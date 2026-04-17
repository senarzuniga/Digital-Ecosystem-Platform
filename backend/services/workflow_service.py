"""
Execution Workflow Service
==========================
Implements the operational detect → decide → act → verify loop.

Key capabilities
----------------
* Idempotent workflow creation (same idempotency_key returns the existing workflow)
* Idempotent action execution  (same action idempotency_key skips already-succeeded actions)
* Retry with configurable max_retries (increments on every re-execute call)
* Human-approval gate  (workflow pauses at WAITING_APPROVAL; resumes after approve())
* Compensation         (on ACT-phase failure, previously executed actions are reversed)
* Full ActionAudit trail for every execution attempt

Supported action types (ACT phase)
-----------------------------------
create_work_order       → CMMS: create a new work order
update_alert_status     → Alert: change alert status (e.g. IN_REVIEW, RESOLVED)
update_asset_status     → Asset: change asset status (e.g. MAINTENANCE)
create_energy_rec       → Energy: generate optimization recommendation
notify                  → Stub: log a notification (extend for email/SMS/webhook)
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.events import Topics, get_event_bus
from backend.models.alert import AlertSeverity, AlertStatus, AlertUpdate
from backend.models.asset import AssetStatus, AssetUpdate
from backend.models.workflow import (
    ActionAudit,
    ActionStatus,
    ExecutionWorkflow,
    WorkflowCreate,
    WorkflowPhase,
    WorkflowState,
    WorkflowTriggerType,
)
from backend.models.work_order import WOPriority, WOType, WorkOrderCreate

logger = logging.getLogger(__name__)

# Cost threshold (cents) above which human approval is auto-required.
APPROVAL_COST_THRESHOLD_CENTS = 100_000  # $1,000

# Estimated cost (cents) per work order by alert severity
_SEVERITY_COST_MAP: dict[str, int] = {
    "critical": 150_000,  # $1,500
    "high":      75_000,  # $750
    "warning":   25_000,  # $250
    "info":       5_000,  # $50
}

# Alert statuses that count as "actioned" during verification
_ACTIONED_ALERT_STATUSES = frozenset({
    AlertStatus.IN_REVIEW,
    AlertStatus.RESOLVED,
    AlertStatus.ACK,
    AlertStatus.AUTO_RESOLVED,
})


# ── CRUD helpers ──────────────────────────────────────────────────────────────

async def create_workflow(
    db: AsyncSession, data: WorkflowCreate, created_by: Optional[str] = None
) -> ExecutionWorkflow:
    """Create a new workflow with idempotency guard."""
    existing = await get_workflow_by_idempotency_key(db, data.idempotency_key)
    if existing is not None:
        logger.info("Workflow already exists for idempotency_key=%s", data.idempotency_key)
        return existing

    wf = ExecutionWorkflow(
        idempotency_key=data.idempotency_key,
        company_id=data.company_id,
        asset_id=data.asset_id,
        trigger_type=data.trigger_type,
        trigger_id=data.trigger_id,
        title=data.title,
        description=data.description,
        requires_approval=data.requires_approval,
        max_retries=data.max_retries,
        created_by=created_by,
    )
    db.add(wf)
    await db.flush()

    bus = get_event_bus()
    await bus.publish(
        Topics.WORKFLOW_CREATED,
        {"workflow_id": wf.id, "company_id": wf.company_id, "title": wf.title},
        source="workflow_service",
    )
    logger.info("Workflow created: id=%s title=%r", wf.id, wf.title)
    return wf


async def get_workflow(db: AsyncSession, workflow_id: str) -> Optional[ExecutionWorkflow]:
    result = await db.execute(
        select(ExecutionWorkflow).where(ExecutionWorkflow.id == workflow_id)
    )
    return result.scalar_one_or_none()


async def get_workflow_by_idempotency_key(
    db: AsyncSession, key: str
) -> Optional[ExecutionWorkflow]:
    result = await db.execute(
        select(ExecutionWorkflow).where(ExecutionWorkflow.idempotency_key == key)
    )
    return result.scalar_one_or_none()


async def list_workflows(
    db: AsyncSession,
    company_id: Optional[str] = None,
    state: Optional[WorkflowState] = None,
    trigger_type: Optional[WorkflowTriggerType] = None,
    limit: int = 50,
    offset: int = 0,
) -> List[ExecutionWorkflow]:
    q = select(ExecutionWorkflow)
    if company_id:
        q = q.where(ExecutionWorkflow.company_id == company_id)
    if state:
        q = q.where(ExecutionWorkflow.state == state)
    if trigger_type:
        q = q.where(ExecutionWorkflow.trigger_type == trigger_type)
    q = q.order_by(ExecutionWorkflow.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(q)
    return list(result.scalars().all())


async def list_action_audits(
    db: AsyncSession,
    workflow_id: Optional[str] = None,
    company_id: Optional[str] = None,
    limit: int = 200,
) -> List[ActionAudit]:
    q = select(ActionAudit)
    if workflow_id:
        q = q.where(ActionAudit.workflow_id == workflow_id)
    if company_id:
        q = q.where(ActionAudit.company_id == company_id)
    q = q.order_by(ActionAudit.executed_at.desc()).limit(limit)
    result = await db.execute(q)
    return list(result.scalars().all())


# ── Approval gate ─────────────────────────────────────────────────────────────

async def approve_workflow(
    db: AsyncSession, workflow_id: str, approved_by: str
) -> ExecutionWorkflow:
    """Approve a workflow that is WAITING_APPROVAL, then execute it."""
    wf = await _require_workflow(db, workflow_id)
    if wf.state != WorkflowState.WAITING_APPROVAL:
        raise ValueError(
            f"Workflow {workflow_id} is not awaiting approval (state={wf.state})"
        )
    wf.state = WorkflowState.APPROVED
    wf.approved_by = approved_by
    wf.approved_at = datetime.now(tz=timezone.utc)
    await db.flush()

    bus = get_event_bus()
    await bus.publish(
        Topics.WORKFLOW_APPROVED,
        {"workflow_id": wf.id, "approved_by": approved_by},
        source="workflow_service",
    )
    # Continue execution from ACT phase
    return await _run_act_and_verify(db, wf)


async def reject_workflow(
    db: AsyncSession, workflow_id: str, user_id: str, reason: str = ""
) -> ExecutionWorkflow:
    """Reject a workflow that is WAITING_APPROVAL."""
    wf = await _require_workflow(db, workflow_id)
    if wf.state != WorkflowState.WAITING_APPROVAL:
        raise ValueError(
            f"Workflow {workflow_id} is not awaiting approval (state={wf.state})"
        )
    wf.state = WorkflowState.REJECTED
    wf.rejection_reason = reason
    wf.completed_at = datetime.now(tz=timezone.utc)
    await db.flush()

    bus = get_event_bus()
    await bus.publish(
        Topics.WORKFLOW_REJECTED,
        {"workflow_id": wf.id, "reason": reason},
        source="workflow_service",
    )
    return wf


async def cancel_workflow(
    db: AsyncSession, workflow_id: str
) -> ExecutionWorkflow:
    """Cancel a workflow that has not yet completed."""
    wf = await _require_workflow(db, workflow_id)
    if wf.state in (
        WorkflowState.COMPLETED,
        WorkflowState.CANCELLED,
        WorkflowState.COMPENSATED,
        WorkflowState.REJECTED,
    ):
        raise ValueError(
            f"Workflow {workflow_id} cannot be cancelled (state={wf.state})"
        )
    wf.state = WorkflowState.CANCELLED
    wf.completed_at = datetime.now(tz=timezone.utc)
    await db.flush()

    bus = get_event_bus()
    await bus.publish(
        Topics.WORKFLOW_CANCELLED,
        {"workflow_id": wf.id},
        source="workflow_service",
    )
    return wf


# ── Main execution entry point ────────────────────────────────────────────────

async def execute_workflow(
    db: AsyncSession, workflow_id: str
) -> ExecutionWorkflow:
    """
    Drive the full detect → decide → act → verify loop.

    * If the workflow requires approval, stops at WAITING_APPROVAL.
    * Call approve_workflow() to resume.
    * Re-calling execute_workflow() on an APPROVED workflow also works.
    """
    wf = await _require_workflow(db, workflow_id)

    if wf.state not in (WorkflowState.PENDING, WorkflowState.APPROVED):
        raise ValueError(
            f"Workflow {workflow_id} cannot be executed (state={wf.state})"
        )

    wf.state = WorkflowState.RUNNING
    wf.started_at = wf.started_at or datetime.now(tz=timezone.utc)
    await db.flush()

    bus = get_event_bus()
    await bus.publish(
        Topics.WORKFLOW_STARTED,
        {"workflow_id": wf.id, "company_id": wf.company_id},
        source="workflow_service",
    )

    try:
        # ── Phase 1: DETECT ───────────────────────────────────────────────────
        wf.current_phase = WorkflowPhase.DETECT
        await db.flush()
        detect_data = await _phase_detect(db, wf)
        wf.set_detect_data(detect_data)
        await db.flush()

        # ── Phase 2: DECIDE ───────────────────────────────────────────────────
        wf.current_phase = WorkflowPhase.DECIDE
        await db.flush()
        decision = await _phase_decide(db, wf, detect_data)
        wf.set_decision_data(decision)
        planned = decision.get("actions", [])
        wf.set_actions_planned(planned)
        await db.flush()

        # ── Approval gate check ───────────────────────────────────────────────
        needs_approval = decision.get("requires_approval", False) or wf.requires_approval
        if needs_approval and wf.state != WorkflowState.APPROVED:
            wf.state = WorkflowState.WAITING_APPROVAL
            wf.requires_approval = True
            await db.flush()
            await bus.publish(
                Topics.WORKFLOW_WAITING_APPROVAL,
                {
                    "workflow_id":  wf.id,
                    "company_id":   wf.company_id,
                    "title":        wf.title,
                    "reason":       decision.get("approval_reason", ""),
                    "planned_actions": len(planned),
                },
                source="workflow_service",
            )
            return wf

        # ── Phase 3 + 4: ACT → VERIFY ─────────────────────────────────────────
        return await _run_act_and_verify(db, wf)

    except Exception as exc:
        wf.state = WorkflowState.FAILED
        wf.error_message = str(exc)
        wf.completed_at = datetime.now(tz=timezone.utc)
        await db.flush()
        await bus.publish(
            Topics.WORKFLOW_FAILED,
            {"workflow_id": wf.id, "error": str(exc)},
            source="workflow_service",
        )
        raise


# ── Internal phase helpers ────────────────────────────────────────────────────

async def _run_act_and_verify(
    db: AsyncSession, wf: ExecutionWorkflow
) -> ExecutionWorkflow:
    """Execute ACT + VERIFY phases.  Called from execute_workflow() and approve_workflow()."""
    bus = get_event_bus()
    try:
        # ── Phase 3: ACT ──────────────────────────────────────────────────────
        wf.state = WorkflowState.RUNNING
        wf.current_phase = WorkflowPhase.ACT
        await db.flush()
        executed = await _phase_act(db, wf)
        wf.set_actions_executed(executed)
        await db.flush()

        # ── Phase 4: VERIFY ───────────────────────────────────────────────────
        wf.current_phase = WorkflowPhase.VERIFY
        await db.flush()
        verification = await _phase_verify(db, wf, executed)
        wf.set_verification_result(verification)

        wf.state = WorkflowState.COMPLETED
        wf.completed_at = datetime.now(tz=timezone.utc)
        await db.flush()

        await bus.publish(
            Topics.WORKFLOW_COMPLETED,
            {
                "workflow_id": wf.id,
                "company_id":  wf.company_id,
                "success":     verification.get("success", True),
                "checks":      verification.get("checks", []),
            },
            source="workflow_service",
        )
        logger.info("Workflow %s completed successfully", wf.id)
        return wf

    except Exception as exc:
        wf.state = WorkflowState.FAILED
        wf.error_message = str(exc)
        wf.completed_at = datetime.now(tz=timezone.utc)
        await db.flush()

        await bus.publish(
            Topics.WORKFLOW_FAILED,
            {"workflow_id": wf.id, "error": str(exc)},
            source="workflow_service",
        )

        # Trigger compensation for any already-executed actions
        await _phase_compensate(db, wf)
        raise


async def _phase_detect(
    db: AsyncSession, wf: ExecutionWorkflow
) -> Dict[str, Any]:
    """
    Gather context about the triggering event.
    For ALERT triggers: enriches with alert severity, category, asset data.
    For MANUAL/AGENT/SCHEDULE: returns lightweight context from workflow fields.
    """
    context: Dict[str, Any] = {
        "trigger_type": wf.trigger_type.value,
        "trigger_id":   wf.trigger_id,
        "company_id":   wf.company_id,
        "asset_id":     wf.asset_id,
        "title":        wf.title,
    }

    if wf.trigger_type == WorkflowTriggerType.ALERT and wf.trigger_id:
        from backend.services.alert_service import get_alert
        alert = await get_alert(db, wf.trigger_id)
        if alert is not None:
            context["alert"] = {
                "id":          alert.id,
                "severity":    alert.severity.value,
                "category":    alert.category.value,
                "title":       alert.title,
                "metric_name": alert.metric_name,
                "metric_value": alert.metric_value,
                "threshold":   alert.threshold,
                "root_cause":  alert.root_cause,
                "recommended_action": alert.recommended_action,
                "asset_id":    alert.asset_id,
            }
            # Propagate asset_id from alert if not already set on workflow
            if alert.asset_id and not wf.asset_id:
                wf.asset_id = alert.asset_id

    return context


async def _phase_decide(
    db: AsyncSession,
    wf: ExecutionWorkflow,
    detect_data: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Determine what actions to take, whether human approval is required,
    and produce an ordered action plan.

    Approval is auto-required when:
      - Alert severity is CRITICAL
      - Any action's estimated cost exceeds APPROVAL_COST_THRESHOLD_CENTS
      - The workflow was explicitly created with requires_approval=True
    """
    actions: List[Dict[str, Any]] = []
    requires_approval = wf.requires_approval
    approval_reason = ""

    alert_data = detect_data.get("alert")
    asset_id    = detect_data.get("asset_id")
    company_id  = detect_data.get("company_id", wf.company_id)

    if alert_data:
        severity = alert_data.get("severity", "warning")
        category = alert_data.get("category", "operational")

        # Determine work order priority from severity
        wo_priority_map = {
            "critical": WOPriority.CRITICAL.value,
            "high":     WOPriority.HIGH.value,
            "warning":  WOPriority.MEDIUM.value,
            "info":     WOPriority.LOW.value,
        }
        wo_priority = wo_priority_map.get(severity, WOPriority.MEDIUM.value)

        # Estimate cost for the work order
        estimated_cost = _SEVERITY_COST_MAP.get(severity, _SEVERITY_COST_MAP["warning"])

        # Always create a work order for alert-driven workflows
        actions.append({
            "type":        "create_work_order",
            "target_type": "work_order",
            "payload": {
                "company_id":     company_id,
                "asset_id":       asset_id,
                "title":          f"[WF] {alert_data.get('title', wf.title)}",
                "description":    (
                    f"Workflow-generated work order.\n\n"
                    f"Root cause: {alert_data.get('root_cause', 'Under investigation')}\n\n"
                    f"Recommended action: {alert_data.get('recommended_action', 'See alert details')}"
                ),
                "wo_type":        "corrective",
                "priority":       wo_priority,
                "alert_id":       alert_data.get("id"),
                "estimated_cost": estimated_cost,
            },
        })

        # Put the alert in review
        if alert_data.get("id"):
            actions.append({
                "type":        "update_alert_status",
                "target_type": "alert",
                "target_id":   alert_data["id"],
                "payload":     {"status": AlertStatus.IN_REVIEW.value},
            })

        # Flag asset as maintenance if severity is critical/high
        if severity in ("critical", "high") and asset_id:
            actions.append({
                "type":        "update_asset_status",
                "target_type": "asset",
                "target_id":   asset_id,
                "payload":     {"status": AssetStatus.MAINTENANCE.value},
            })

        # Auto-require approval for critical alerts or high estimated cost
        if severity == "critical":
            requires_approval = True
            approval_reason = "Critical alert severity requires human approval before execution"
        elif estimated_cost >= APPROVAL_COST_THRESHOLD_CENTS:
            requires_approval = True
            approval_reason = (
                f"Estimated cost ${estimated_cost / 100:.0f} exceeds approval threshold "
                f"${APPROVAL_COST_THRESHOLD_CENTS / 100:.0f}"
            )

    else:
        # MANUAL / SCHEDULE / AGENT workflow with no alert data
        # Default: create an inspection work order if asset is specified
        if asset_id:
            actions.append({
                "type":        "create_work_order",
                "target_type": "work_order",
                "payload": {
                    "company_id": company_id,
                    "asset_id":   asset_id,
                    "title":      f"[WF] {wf.title}",
                    "description": wf.description or "Workflow-generated work order",
                    "wo_type":    WOType.INSPECTION.value,
                    "priority":   WOPriority.MEDIUM.value,
                },
            })
        else:
            # No asset: record a notification-only action
            actions.append({
                "type":        "notify",
                "target_type": "system",
                "payload": {
                    "company_id": company_id,
                    "message":    f"Workflow '{wf.title}' completed decision phase: no asset-level actions required.",
                },
            })

    return {
        "requires_approval": requires_approval,
        "approval_reason":   approval_reason,
        "actions":           actions,
    }


async def _phase_act(
    db: AsyncSession, wf: ExecutionWorkflow
) -> List[Dict[str, Any]]:
    """
    Execute each planned action with idempotency + retry.
    Returns a list of execution summaries (one per action).
    """
    planned = wf.get_actions_planned()
    executed: List[Dict[str, Any]] = []

    for idx, action in enumerate(planned):
        action_key = f"{wf.id}:{action['type']}:{idx}"
        audit = await _execute_with_retry(db, wf, action, action_key)
        executed.append({
            "audit_id":  audit.id,
            "type":      audit.action_type,
            "status":    audit.status.value,
            "target_id": audit.target_id,
        })

    return executed


async def _phase_verify(
    db: AsyncSession,
    wf: ExecutionWorkflow,
    executed: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Verify that executed actions produced the expected side-effects.
    Returns {success: bool, checks: [{action, verified, detail}]}.
    """
    checks = []
    all_ok = True

    for item in executed:
        action_type = item["type"]
        target_id   = item.get("target_id")
        status      = item.get("status", "")
        verified    = False
        detail      = ""

        if status != ActionStatus.SUCCESS.value:
            verified = False
            detail   = f"Action did not complete successfully (status={status})"
            all_ok   = False
        elif action_type == "create_work_order" and target_id:
            from backend.services.cmms_service import get_work_order
            wo = await get_work_order(db, target_id)
            verified = wo is not None
            detail   = f"Work order {target_id} exists: {verified}"
            if not verified:
                all_ok = False
        elif action_type == "update_alert_status" and target_id:
            from backend.services.alert_service import get_alert
            alert = await get_alert(db, target_id)
            verified = alert is not None and alert.status in _ACTIONED_ALERT_STATUSES
            detail = f"Alert {target_id} status is {alert.status.value if alert else 'NOT FOUND'}"
            if not verified:
                all_ok = False
        elif action_type == "update_asset_status" and target_id:
            from backend.services.data_service import get_asset
            asset = await get_asset(db, target_id)
            verified = asset is not None
            detail   = f"Asset {target_id} found: {verified}"
        else:
            # Notification and other stub actions — always verified
            verified = True
            detail   = f"Action '{action_type}' accepted"

        checks.append({"action": action_type, "target_id": target_id, "verified": verified, "detail": detail})

    return {"success": all_ok, "checks": checks}


async def _phase_compensate(
    db: AsyncSession, wf: ExecutionWorkflow
) -> None:
    """
    Reverse successfully-executed actions (in LIFO order).
    Sets workflow state to COMPENSATING → COMPENSATED.
    """
    wf.state = WorkflowState.COMPENSATING
    await db.flush()

    executed = wf.get_actions_executed()
    # Process in reverse order
    for item in reversed(executed):
        if item.get("status") != ActionStatus.SUCCESS.value:
            continue
        action_type = item["type"]
        target_id   = item.get("target_id")

        try:
            if action_type == "create_work_order" and target_id:
                from backend.services import cmms_service
                from backend.models.work_order import WorkOrderUpdate, WOStatus
                await cmms_service.update_work_order(
                    db, target_id, WorkOrderUpdate(status=WOStatus.CANCELLED)
                )
                logger.info("Compensated work order %s (cancelled)", target_id)

            elif action_type == "update_alert_status" and target_id:
                from backend.services.alert_service import update_alert
                from backend.models.alert import AlertUpdate, AlertStatus
                await update_alert(db, target_id, AlertUpdate(status=AlertStatus.OPEN))
                logger.info("Compensated alert %s (reverted to OPEN)", target_id)

            elif action_type == "update_asset_status" and target_id:
                from backend.services.data_service import update_asset
                from backend.models.asset import AssetUpdate, AssetStatus
                await update_asset(db, target_id, AssetUpdate(status=AssetStatus.ONLINE))
                logger.info("Compensated asset %s (reverted to ONLINE)", target_id)

            else:
                logger.info("No compensation defined for action type '%s'", action_type)

        except Exception as exc:
            logger.error(
                "Compensation failed for action '%s' target=%s: %s",
                action_type, target_id, exc,
            )

    wf.state = WorkflowState.COMPENSATED
    await db.flush()

    bus = get_event_bus()
    await bus.publish(
        Topics.WORKFLOW_COMPENSATED,
        {"workflow_id": wf.id, "compensated_actions": len(executed)},
        source="workflow_service",
    )
    logger.info("Workflow %s compensated (%d actions reversed)", wf.id, len(executed))


# ── Idempotent action executor with retry ─────────────────────────────────────

async def _execute_with_retry(
    db: AsyncSession,
    wf: ExecutionWorkflow,
    action: Dict[str, Any],
    idempotency_key: str,
) -> ActionAudit:
    """
    Execute a single action with idempotency and retry logic.

    1. Check if a successful audit record already exists for this idempotency_key.
       If so, return it immediately (idempotent re-execution safe).
    2. Attempt execution up to wf.max_retries times, writing one ActionAudit
       per attempt.
    3. Raise on final failure (triggers compensation in the caller).
    """
    # Idempotency: skip if already succeeded
    prior = await _get_audit_by_idempotency_key(db, idempotency_key)
    if prior is not None and prior.status == ActionStatus.SUCCESS:
        logger.info("Action '%s' already succeeded (audit=%s); skipping", action["type"], prior.id)
        prior_skipped = ActionAudit(
            workflow_id=wf.id,
            company_id=wf.company_id,
            asset_id=wf.asset_id,
            actor_type="system",
            actor_id=wf.created_by,
            action_type=action["type"],
            target_type=action.get("target_type"),
            target_id=prior.target_id,
            idempotency_key=idempotency_key,
            status=ActionStatus.SKIPPED,
            attempt_number=0,
            input_payload=json.dumps(action.get("payload", {})),
            output_payload=prior.output_payload,
        )
        db.add(prior_skipped)
        await db.flush()
        return prior_skipped

    last_exc: Optional[Exception] = None
    for attempt in range(1, wf.max_retries + 1):
        t_start = datetime.now(tz=timezone.utc)
        audit = ActionAudit(
            workflow_id=wf.id,
            company_id=wf.company_id,
            asset_id=wf.asset_id,
            actor_type="system",
            actor_id=wf.created_by,
            action_type=action["type"],
            target_type=action.get("target_type"),
            target_id=action.get("target_id"),
            idempotency_key=idempotency_key,
            status=ActionStatus.EXECUTING,
            attempt_number=attempt,
            input_payload=json.dumps(action.get("payload", {})),
        )
        db.add(audit)
        await db.flush()

        try:
            result = await _dispatch_action(db, action)
            t_end = datetime.now(tz=timezone.utc)
            duration = int((t_end - t_start).total_seconds() * 1000)
            audit.status      = ActionStatus.SUCCESS
            audit.output_payload = json.dumps(result)
            audit.target_id   = (
                result.get("id") or result.get("work_order_id") or action.get("target_id")
            )
            audit.duration_ms = duration
            await db.flush()

            bus = get_event_bus()
            await bus.publish(
                Topics.ACTION_EXECUTED,
                {
                    "audit_id":    audit.id,
                    "workflow_id": wf.id,
                    "action_type": audit.action_type,
                    "status":      "success",
                },
                source="workflow_service",
            )
            return audit

        except Exception as exc:
            last_exc = exc
            t_end = datetime.now(tz=timezone.utc)
            duration = int((t_end - t_start).total_seconds() * 1000)
            audit.status      = ActionStatus.FAILED
            audit.error_message = str(exc)
            audit.duration_ms = duration
            await db.flush()

            wf.retry_count += 1
            await db.flush()

            logger.warning(
                "Action '%s' attempt %d/%d failed: %s",
                action["type"], attempt, wf.max_retries, exc,
            )
            if attempt < wf.max_retries:
                # In a real system: asyncio.sleep(2 ** attempt)
                # Skipped here to keep tests fast.
                pass

    raise last_exc or RuntimeError(
        f"Action '{action['type']}' failed after {wf.max_retries} attempts"
    )


async def _dispatch_action(
    db: AsyncSession, action: Dict[str, Any]
) -> Dict[str, Any]:
    """Route an action to the appropriate service function."""
    action_type = action["type"]
    payload     = action.get("payload", {})

    if action_type == "create_work_order":
        from backend.services import cmms_service
        wo = await cmms_service.create_work_order(
            db,
            WorkOrderCreate(
                company_id=payload["company_id"],
                asset_id=payload.get("asset_id"),
                title=payload.get("title", "Workflow work order"),
                description=payload.get("description"),
                wo_type=payload.get("wo_type", WOType.CORRECTIVE.value),
                priority=payload.get("priority", WOPriority.MEDIUM.value),
                alert_id=payload.get("alert_id"),
                estimated_cost=payload.get("estimated_cost"),
            ),
            created_by="workflow_engine",
        )
        return {"id": wo.id, "wo_number": wo.wo_number}

    if action_type == "update_alert_status":
        from backend.services.alert_service import get_alert, update_alert
        from backend.models.alert import AlertUpdate
        alert_id = action.get("target_id")
        if not alert_id:
            raise ValueError("update_alert_status requires target_id")
        updated = await update_alert(
            db,
            alert_id,
            AlertUpdate(status=payload.get("status")),
        )
        if updated is None:
            raise ValueError(f"Alert {alert_id} not found")
        return {"id": alert_id, "status": updated.status.value}

    if action_type == "update_asset_status":
        from backend.services.data_service import get_asset, update_asset
        from backend.models.asset import AssetUpdate
        asset_id = action.get("target_id")
        if not asset_id:
            raise ValueError("update_asset_status requires target_id")
        updated = await update_asset(
            db,
            asset_id,
            AssetUpdate(status=payload.get("status")),
        )
        if updated is None:
            raise ValueError(f"Asset {asset_id} not found")
        return {"id": asset_id, "status": payload.get("status")}

    if action_type == "create_energy_rec":
        from backend.services.energy_service import generate_recommendations
        recs = await generate_recommendations(db, payload["company_id"])
        return {"recommendations_generated": len(recs)}

    if action_type == "notify":
        # Stub: in production dispatch email/SMS/webhook
        logger.info(
            "NOTIFY [company=%s]: %s",
            payload.get("company_id"), payload.get("message"),
        )
        return {"notified": True, "message": payload.get("message", "")}

    raise ValueError(f"Unknown action type: '{action_type}'")


# ── Internal helpers ──────────────────────────────────────────────────────────

async def _require_workflow(
    db: AsyncSession, workflow_id: str
) -> ExecutionWorkflow:
    wf = await get_workflow(db, workflow_id)
    if wf is None:
        raise ValueError(f"Workflow {workflow_id} not found")
    return wf


async def _get_audit_by_idempotency_key(
    db: AsyncSession, key: str
) -> Optional[ActionAudit]:
    result = await db.execute(
        select(ActionAudit)
        .where(ActionAudit.idempotency_key == key, ActionAudit.status == ActionStatus.SUCCESS)
        .limit(1)
    )
    return result.scalar_one_or_none()
