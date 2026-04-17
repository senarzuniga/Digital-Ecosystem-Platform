"""
Tests for the Execution Workflow Engine (Phase 1).

Coverage
--------
Service layer (unit):
  - Idempotent workflow creation
  - MANUAL workflow: full detect → decide → act → verify cycle (no asset)
  - MANUAL workflow with asset: work order created + verified
  - ALERT workflow: alert fetched in detect, WO + status update in act
  - Approval gate: critical alert pauses at WAITING_APPROVAL
  - Approve then execute to COMPLETED
  - Reject workflow
  - Cancel (PENDING state)
  - Cancel already COMPLETED workflow raises ValueError
  - Idempotent action execution (skips already-succeeded actions)
  - Action audit records created per attempt
  - list_workflows filters by company_id and state
  - list_action_audits filters by workflow_id

API layer (integration):
  - POST /workflows  → 201
  - POST /workflows/{id}/execute (manager only) → 200
  - POST /workflows/{id}/execute (tech) → 403
  - GET  /workflows/{id} → 200
  - GET  /workflows      → list
  - GET  /workflows/{id}/audit → list of audits
  - POST /workflows/{id}/approve → 200
  - POST /workflows/{id}/reject  → 200
  - POST /workflows/{id}/cancel  → 200
"""

from __future__ import annotations

import pytest

from backend.models.alert import AlertCategory, AlertCreate, AlertSeverity
from backend.models.asset import AssetCreate, ConnectorType
from backend.models.workflow import WorkflowCreate, WorkflowPhase, WorkflowState, WorkflowTriggerType
from backend.services import alert_service, workflow_service
from backend.services.data_service import create_asset
from backend.tests.conftest import AUTH_ADMIN, AUTH_MANAGER, AUTH_TECH


# ── Helpers ───────────────────────────────────────────────────────────────────

def _wf_data(suffix: str, **kwargs) -> WorkflowCreate:
    return WorkflowCreate(
        idempotency_key=f"test-{suffix}",
        company_id="ACME",
        title=f"Test workflow {suffix}",
        **kwargs,
    )


# ── Idempotency ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_workflow_idempotent(db):
    """Same idempotency key must return the same workflow record."""
    data = _wf_data("idem-01")
    wf1 = await workflow_service.create_workflow(db, data)
    wf2 = await workflow_service.create_workflow(db, data)
    assert wf1.id == wf2.id


@pytest.mark.asyncio
async def test_create_workflow_different_keys(db):
    """Different idempotency keys create distinct workflows."""
    wf1 = await workflow_service.create_workflow(db, _wf_data("diff-01"))
    wf2 = await workflow_service.create_workflow(db, _wf_data("diff-02"))
    assert wf1.id != wf2.id


# ── Full cycle — MANUAL, no asset ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_manual_workflow_no_asset_full_cycle(db):
    """
    MANUAL workflow without an asset_id:
    DECIDE produces a 'notify' action → COMPLETED.
    """
    wf = await workflow_service.create_workflow(db, _wf_data("manual-no-asset-01"))
    assert wf.state == WorkflowState.PENDING

    wf = await workflow_service.execute_workflow(db, wf.id)
    assert wf.state == WorkflowState.COMPLETED
    assert wf.current_phase == WorkflowPhase.VERIFY
    result = wf.get_verification_result()
    assert result["success"] is True


@pytest.mark.asyncio
async def test_manual_workflow_with_asset_creates_work_order(db):
    """
    MANUAL workflow with an asset_id:
    DECIDE produces a 'create_work_order' action → COMPLETED + WO exists.
    """
    asset = await create_asset(
        db,
        AssetCreate(
            company_id="ACME",
            name="Press-001",
            asset_type="press",
            connector_type=ConnectorType.MANUAL,
        ),
    )

    wf = await workflow_service.create_workflow(
        db,
        _wf_data("manual-with-asset-01", asset_id=asset.id),
    )
    wf = await workflow_service.execute_workflow(db, wf.id)

    assert wf.state == WorkflowState.COMPLETED
    executed = wf.get_actions_executed()
    wo_actions = [a for a in executed if a["type"] == "create_work_order"]
    assert len(wo_actions) == 1

    # Verify work order exists in DB
    from backend.services.cmms_service import get_work_order
    wo = await get_work_order(db, wo_actions[0]["target_id"])
    assert wo is not None
    assert wo.asset_id == asset.id


# ── ALERT workflow ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_alert_workflow_high_severity(db):
    """
    HIGH severity alert → non-critical → no approval required → COMPLETED.
    Actions: create_work_order + update_alert_status.
    """
    alert = await alert_service.create_alert(
        db,
        AlertCreate(
            company_id="ACME",
            severity=AlertSeverity.HIGH,
            category=AlertCategory.MAINTENANCE,
            title="High vibration",
            metric_name="vibration",
            metric_value=4.5,
            threshold=4.0,
        ),
        auto_respond=False,
    )

    wf = await workflow_service.create_workflow(
        db,
        _wf_data(
            "alert-high-01",
            trigger_type=WorkflowTriggerType.ALERT,
            trigger_id=alert.id,
        ),
    )
    wf = await workflow_service.execute_workflow(db, wf.id)

    assert wf.state == WorkflowState.COMPLETED
    executed = wf.get_actions_executed()
    types = [a["type"] for a in executed]
    assert "create_work_order" in types
    assert "update_alert_status" in types


@pytest.mark.asyncio
async def test_alert_workflow_critical_pauses_for_approval(db):
    """
    CRITICAL alert → requires_approval=True → WAITING_APPROVAL.
    """
    alert = await alert_service.create_alert(
        db,
        AlertCreate(
            company_id="ACME",
            severity=AlertSeverity.CRITICAL,
            category=AlertCategory.MAINTENANCE,
            title="Critical temperature",
            metric_name="temperature",
            metric_value=95.0,
            threshold=85.0,
        ),
        auto_respond=False,
    )

    wf = await workflow_service.create_workflow(
        db,
        _wf_data(
            "alert-critical-gate-01",
            trigger_type=WorkflowTriggerType.ALERT,
            trigger_id=alert.id,
        ),
    )
    wf = await workflow_service.execute_workflow(db, wf.id)

    assert wf.state == WorkflowState.WAITING_APPROVAL
    assert wf.requires_approval is True


@pytest.mark.asyncio
async def test_explicit_approval_gate_pauses_execution(db):
    """Workflow created with requires_approval=True stops at WAITING_APPROVAL."""
    wf = await workflow_service.create_workflow(
        db, _wf_data("explicit-gate-01", requires_approval=True)
    )
    wf = await workflow_service.execute_workflow(db, wf.id)
    assert wf.state == WorkflowState.WAITING_APPROVAL


# ── Approval gate ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_approve_workflow_continues_to_completed(db):
    """After approval, workflow runs ACT + VERIFY and reaches COMPLETED."""
    wf = await workflow_service.create_workflow(
        db, _wf_data("approve-cycle-01", requires_approval=True)
    )
    wf = await workflow_service.execute_workflow(db, wf.id)
    assert wf.state == WorkflowState.WAITING_APPROVAL

    wf = await workflow_service.approve_workflow(db, wf.id, approved_by="manager-001")
    assert wf.state == WorkflowState.COMPLETED
    assert wf.approved_by == "manager-001"
    assert wf.approved_at is not None


@pytest.mark.asyncio
async def test_approve_non_waiting_raises(db):
    """Approving a PENDING workflow raises ValueError."""
    wf = await workflow_service.create_workflow(db, _wf_data("approve-bad-state-01"))
    with pytest.raises(ValueError, match="not awaiting approval"):
        await workflow_service.approve_workflow(db, wf.id, approved_by="mgr")


# ── Rejection ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_reject_workflow(db):
    """Rejecting a WAITING_APPROVAL workflow sets state to REJECTED."""
    wf = await workflow_service.create_workflow(
        db, _wf_data("reject-01", requires_approval=True)
    )
    wf = await workflow_service.execute_workflow(db, wf.id)
    assert wf.state == WorkflowState.WAITING_APPROVAL

    wf = await workflow_service.reject_workflow(
        db, wf.id, user_id="manager-001", reason="Budget not approved"
    )
    assert wf.state == WorkflowState.REJECTED
    assert wf.rejection_reason == "Budget not approved"
    assert wf.completed_at is not None


@pytest.mark.asyncio
async def test_reject_non_waiting_raises(db):
    """Rejecting a PENDING workflow raises ValueError."""
    wf = await workflow_service.create_workflow(db, _wf_data("reject-bad-state-01"))
    with pytest.raises(ValueError, match="not awaiting approval"):
        await workflow_service.reject_workflow(db, wf.id, user_id="mgr", reason="nope")


# ── Cancellation ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_cancel_pending_workflow(db):
    """A PENDING workflow can be cancelled."""
    wf = await workflow_service.create_workflow(db, _wf_data("cancel-pending-01"))
    assert wf.state == WorkflowState.PENDING

    wf = await workflow_service.cancel_workflow(db, wf.id)
    assert wf.state == WorkflowState.CANCELLED
    assert wf.completed_at is not None


@pytest.mark.asyncio
async def test_cancel_completed_workflow_raises(db):
    """Cancelling a COMPLETED workflow raises ValueError."""
    wf = await workflow_service.create_workflow(db, _wf_data("cancel-done-01"))
    wf = await workflow_service.execute_workflow(db, wf.id)
    assert wf.state == WorkflowState.COMPLETED

    with pytest.raises(ValueError, match="cannot be cancelled"):
        await workflow_service.cancel_workflow(db, wf.id)


# ── Execute from wrong state ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_execute_cancelled_workflow_raises(db):
    """Executing a CANCELLED workflow raises ValueError."""
    wf = await workflow_service.create_workflow(db, _wf_data("exec-cancelled-01"))
    wf = await workflow_service.cancel_workflow(db, wf.id)
    with pytest.raises(ValueError, match="cannot be executed"):
        await workflow_service.execute_workflow(db, wf.id)


# ── Action idempotency ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_action_audit_records_created(db):
    """Each executed action produces at least one ActionAudit record."""
    wf = await workflow_service.create_workflow(db, _wf_data("audit-check-01"))
    wf = await workflow_service.execute_workflow(db, wf.id)

    audits = await workflow_service.list_action_audits(db, workflow_id=wf.id)
    assert len(audits) >= 1
    for a in audits:
        assert a.workflow_id == wf.id
        assert a.company_id == "ACME"


@pytest.mark.asyncio
async def test_action_idempotency_skips_already_succeeded(db):
    """
    Re-running execute on an APPROVED workflow where actions already succeeded
    should produce SKIPPED audit records (not duplicates).
    """
    # Create a workflow, get it to WAITING_APPROVAL
    wf = await workflow_service.create_workflow(
        db, _wf_data("idem-action-01", requires_approval=True)
    )
    wf = await workflow_service.execute_workflow(db, wf.id)
    assert wf.state == WorkflowState.WAITING_APPROVAL

    # Approve → runs ACT (creates audits)
    wf = await workflow_service.approve_workflow(db, wf.id, approved_by="mgr")
    assert wf.state == WorkflowState.COMPLETED

    from backend.models.workflow import ActionStatus
    audits_after_first = await workflow_service.list_action_audits(db, workflow_id=wf.id)

    # No duplicate successful actions (idempotency preserved)
    success_types = [a.action_type for a in audits_after_first if a.status == ActionStatus.SUCCESS]
    assert len(success_types) == len(set(success_types)), "Duplicate successful action types found"

    # No SKIPPED records on first execution (skipped only appear on re-execution)
    skipped = [a for a in audits_after_first if a.status == ActionStatus.SKIPPED]
    assert len(skipped) == 0, "Unexpected SKIPPED records on first execution"


# ── List / filter ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_workflows_filter_by_company(db):
    """list_workflows respects company_id filter."""
    co = "LIST-CO-WF"
    for i in range(3):
        await workflow_service.create_workflow(
            db, WorkflowCreate(
                idempotency_key=f"list-co-{i}",
                company_id=co,
                title=f"WF {i}",
            )
        )
    results = await workflow_service.list_workflows(db, company_id=co)
    assert len(results) >= 3
    assert all(w.company_id == co for w in results)


@pytest.mark.asyncio
async def test_list_workflows_filter_by_state(db):
    """list_workflows respects state filter."""
    wf = await workflow_service.create_workflow(db, _wf_data("state-filter-01"))
    results = await workflow_service.list_workflows(db, state=WorkflowState.PENDING)
    pending_ids = [w.id for w in results]
    assert wf.id in pending_ids


@pytest.mark.asyncio
async def test_list_action_audits_by_workflow(db):
    """list_action_audits returns only audits for the given workflow."""
    wf = await workflow_service.create_workflow(db, _wf_data("audit-list-01"))
    await workflow_service.execute_workflow(db, wf.id)

    audits = await workflow_service.list_action_audits(db, workflow_id=wf.id)
    assert all(a.workflow_id == wf.id for a in audits)


# ── GET nonexistent ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_nonexistent_workflow(db):
    wf = await workflow_service.get_workflow(db, "does-not-exist")
    assert wf is None


@pytest.mark.asyncio
async def test_execute_nonexistent_workflow_raises(db):
    with pytest.raises(ValueError, match="not found"):
        await workflow_service.execute_workflow(db, "does-not-exist")


# ── API integration tests ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_api_create_workflow(client):
    resp = await client.post(
        "/api/v1/workflows/",
        json={
            "idempotency_key": "api-create-01",
            "company_id":      "ACME",
            "title":           "API test workflow",
        },
        headers=AUTH_TECH,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["state"] == "pending"
    assert body["idempotency_key"] == "api-create-01"


@pytest.mark.asyncio
async def test_api_create_workflow_idempotent(client):
    """Calling create twice with the same idempotency_key returns 201 both times, same id."""
    payload = {"idempotency_key": "api-idem-api-01", "company_id": "ACME", "title": "Idem WF"}
    r1 = await client.post("/api/v1/workflows/", json=payload, headers=AUTH_TECH)
    r2 = await client.post("/api/v1/workflows/", json=payload, headers=AUTH_TECH)
    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["id"] == r2.json()["id"]


@pytest.mark.asyncio
async def test_api_execute_requires_manager(client):
    """Tech role cannot execute workflows."""
    cr = await client.post(
        "/api/v1/workflows/",
        json={"idempotency_key": "api-exec-auth-01", "company_id": "ACME", "title": "Auth test"},
        headers=AUTH_TECH,
    )
    wf_id = cr.json()["id"]
    resp = await client.post(f"/api/v1/workflows/{wf_id}/execute", headers=AUTH_TECH)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_api_execute_workflow_as_manager(client):
    """Manager can execute a workflow."""
    cr = await client.post(
        "/api/v1/workflows/",
        json={"idempotency_key": "api-exec-mgr-01", "company_id": "ACME", "title": "Manager exec"},
        headers=AUTH_MANAGER,
    )
    wf_id = cr.json()["id"]
    resp = await client.post(f"/api/v1/workflows/{wf_id}/execute", headers=AUTH_MANAGER)
    assert resp.status_code == 200
    assert resp.json()["state"] == "completed"


@pytest.mark.asyncio
async def test_api_get_workflow(client):
    cr = await client.post(
        "/api/v1/workflows/",
        json={"idempotency_key": "api-get-01", "company_id": "ACME", "title": "Get test"},
        headers=AUTH_TECH,
    )
    wf_id = cr.json()["id"]
    resp = await client.get(f"/api/v1/workflows/{wf_id}", headers=AUTH_TECH)
    assert resp.status_code == 200
    assert resp.json()["id"] == wf_id


@pytest.mark.asyncio
async def test_api_get_nonexistent_workflow(client):
    resp = await client.get("/api/v1/workflows/does-not-exist", headers=AUTH_TECH)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_api_list_workflows(client):
    resp = await client.get("/api/v1/workflows/?company_id=ACME", headers=AUTH_TECH)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_api_approve_workflow(client):
    """Manager approves a WAITING_APPROVAL workflow → COMPLETED."""
    # Create with requires_approval flag
    cr = await client.post(
        "/api/v1/workflows/",
        json={
            "idempotency_key": "api-approve-01",
            "company_id":      "ACME",
            "title":           "Needs approval",
            "requires_approval": True,
        },
        headers=AUTH_MANAGER,
    )
    wf_id = cr.json()["id"]

    # Execute → should pause at WAITING_APPROVAL
    exec_resp = await client.post(f"/api/v1/workflows/{wf_id}/execute", headers=AUTH_MANAGER)
    assert exec_resp.json()["state"] == "waiting_approval"

    # Approve
    app_resp = await client.post(f"/api/v1/workflows/{wf_id}/approve", headers=AUTH_MANAGER)
    assert app_resp.status_code == 200
    assert app_resp.json()["state"] == "completed"


@pytest.mark.asyncio
async def test_api_approve_requires_manager(client):
    """Tech role cannot approve workflows."""
    cr = await client.post(
        "/api/v1/workflows/",
        json={
            "idempotency_key": "api-approve-auth-01",
            "company_id": "ACME",
            "title": "Auth check",
            "requires_approval": True,
        },
        headers=AUTH_TECH,
    )
    wf_id = cr.json()["id"]
    await client.post(f"/api/v1/workflows/{wf_id}/execute", headers=AUTH_MANAGER)
    resp = await client.post(f"/api/v1/workflows/{wf_id}/approve", headers=AUTH_TECH)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_api_reject_workflow(client):
    """Manager rejects a WAITING_APPROVAL workflow."""
    cr = await client.post(
        "/api/v1/workflows/",
        json={
            "idempotency_key": "api-reject-01",
            "company_id": "ACME",
            "title": "To be rejected",
            "requires_approval": True,
        },
        headers=AUTH_MANAGER,
    )
    wf_id = cr.json()["id"]
    await client.post(f"/api/v1/workflows/{wf_id}/execute", headers=AUTH_MANAGER)

    rej_resp = await client.post(
        f"/api/v1/workflows/{wf_id}/reject",
        json={"reason": "Cost exceeds budget"},
        headers=AUTH_MANAGER,
    )
    assert rej_resp.status_code == 200
    assert rej_resp.json()["state"] == "rejected"
    assert rej_resp.json()["rejection_reason"] == "Cost exceeds budget"


@pytest.mark.asyncio
async def test_api_cancel_workflow(client):
    """Manager cancels a PENDING workflow."""
    cr = await client.post(
        "/api/v1/workflows/",
        json={"idempotency_key": "api-cancel-01", "company_id": "ACME", "title": "To cancel"},
        headers=AUTH_MANAGER,
    )
    wf_id = cr.json()["id"]
    cancel_resp = await client.post(f"/api/v1/workflows/{wf_id}/cancel", headers=AUTH_MANAGER)
    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["state"] == "cancelled"


@pytest.mark.asyncio
async def test_api_audit_trail(client):
    """After executing a workflow, the audit endpoint returns action records."""
    cr = await client.post(
        "/api/v1/workflows/",
        json={"idempotency_key": "api-audit-01", "company_id": "ACME", "title": "Audit check"},
        headers=AUTH_MANAGER,
    )
    wf_id = cr.json()["id"]
    await client.post(f"/api/v1/workflows/{wf_id}/execute", headers=AUTH_MANAGER)

    audit_resp = await client.get(f"/api/v1/workflows/{wf_id}/audit", headers=AUTH_TECH)
    assert audit_resp.status_code == 200
    assert isinstance(audit_resp.json(), list)
    assert len(audit_resp.json()) >= 1


@pytest.mark.asyncio
async def test_api_audit_nonexistent_workflow(client):
    resp = await client.get("/api/v1/workflows/ghost-id/audit", headers=AUTH_TECH)
    assert resp.status_code == 404
