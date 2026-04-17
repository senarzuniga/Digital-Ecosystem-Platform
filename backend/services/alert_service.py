"""
Alert Service — classification, root cause analysis, auto-response workflows.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.events import Topics, get_event_bus
from backend.models.alert import (
    Alert,
    AlertCategory,
    AlertCreate,
    AlertSeverity,
    AlertStatus,
    AlertUpdate,
)
from backend.models.work_order import WOPriority, WOType, WorkOrderCreate
from backend.services import cmms_service

logger = logging.getLogger(__name__)

# ── Rule-based thresholds ─────────────────────────────────────────────────────
_THRESHOLD_RULES: list[dict] = [
    {"metric": "temperature", "threshold": 85.0, "severity": AlertSeverity.CRITICAL, "category": AlertCategory.OPERATIONAL,  "title": "Critical temperature exceeded"},
    {"metric": "temperature", "threshold": 75.0, "severity": AlertSeverity.WARNING,  "category": AlertCategory.OPERATIONAL,  "title": "High temperature warning"},
    {"metric": "vibration",   "threshold": 4.0,  "severity": AlertSeverity.CRITICAL, "category": AlertCategory.MAINTENANCE,  "title": "Critical vibration level"},
    {"metric": "vibration",   "threshold": 3.0,  "severity": AlertSeverity.WARNING,  "category": AlertCategory.MAINTENANCE,  "title": "Elevated vibration detected"},
    {"metric": "oee",         "threshold": 60.0, "severity": AlertSeverity.WARNING,  "category": AlertCategory.OPERATIONAL,  "title": "OEE below 60% threshold", "inverted": True},
    {"metric": "power_kw",    "threshold": 70.0, "severity": AlertSeverity.WARNING,  "category": AlertCategory.ENERGY,       "title": "High power consumption"},
]

# ── Root Cause templates ───────────────────────────────────────────────────────
_ROOT_CAUSE_MAP: dict[str, str] = {
    "temperature": "Likely causes: insufficient coolant flow, blocked ventilation, or overloaded motor.",
    "vibration":   "Likely causes: bearing wear, misalignment, imbalanced rotating parts, or loose fasteners.",
    "oee":         "Likely causes: unplanned downtime, slow cycle time, or quality rejects exceeding target.",
    "power_kw":    "Likely causes: degraded motor efficiency, process overload, or leakage in hydraulic system.",
}

# ── Recommended actions ────────────────────────────────────────────────────────
_ACTION_MAP: dict[str, str] = {
    "temperature": "Inspect coolant circuit, clear air vents, reduce load. Schedule maintenance within 4 hours.",
    "vibration":   "Inspect and replace bearings. Perform dynamic balancing. Check coupling alignment.",
    "oee":         "Review shift logs for unplanned stops. Analyse quality rejection data. Assign engineering review.",
    "power_kw":    "Measure individual load components. Check for hydraulic leaks. Consider load redistribution.",
}


async def create_alert(
    db: AsyncSession, data: AlertCreate, auto_respond: bool = True
) -> Alert:
    alert = Alert(
        company_id=data.company_id,
        asset_id=data.asset_id,
        severity=data.severity,
        category=data.category,
        title=data.title,
        description=data.description,
        metric_name=data.metric_name,
        metric_value=data.metric_value,
        threshold=data.threshold,
        source=data.source or "manual",
        recommended_action=data.recommended_action,
    )

    # Enrich with root cause
    if data.metric_name and alert.root_cause is None:
        alert.root_cause = _ROOT_CAUSE_MAP.get(data.metric_name)
    if data.metric_name and alert.recommended_action is None:
        alert.recommended_action = _ACTION_MAP.get(data.metric_name)

    db.add(alert)
    await db.flush()

    bus = get_event_bus()
    await bus.publish(
        Topics.MACHINE_ALERT_TRIGGERED,
        {
            "alert_id": alert.id,
            "company_id": alert.company_id,
            "asset_id": alert.asset_id,
            "severity": alert.severity.value,
            "category": alert.category.value,
            "title": alert.title,
        },
        source="alert_service",
    )

    # Auto-response: create work order for CRITICAL/HIGH maintenance alerts
    if auto_respond and alert.severity in (AlertSeverity.CRITICAL, AlertSeverity.HIGH):
        if alert.category in (AlertCategory.MAINTENANCE, AlertCategory.OPERATIONAL):
            await _auto_create_work_order(db, alert)

    logger.info("Alert created: id=%s severity=%s", alert.id, alert.severity)
    return alert


async def _auto_create_work_order(db: AsyncSession, alert: Alert) -> None:
    priority = WOPriority.CRITICAL if alert.severity == AlertSeverity.CRITICAL else WOPriority.HIGH
    wo_data = WorkOrderCreate(
        company_id=alert.company_id,
        asset_id=alert.asset_id,
        title=f"[AUTO] {alert.title}",
        description=f"Work order auto-generated from alert {alert.id}.\n\n"
                    f"Root cause: {alert.root_cause or 'Under investigation'}\n\n"
                    f"Recommended action: {alert.recommended_action or 'See alert details'}",
        wo_type=WOType.CORRECTIVE,
        priority=priority,
        alert_id=alert.id,
    )
    wo = await cmms_service.create_work_order(db, wo_data, created_by="system")
    alert.work_order_id = wo.id
    alert.auto_actioned = True
    await db.flush()
    logger.info("Auto-created work order %s for alert %s", wo.wo_number, alert.id)


async def check_telemetry_thresholds(
    db: AsyncSession,
    company_id: str,
    asset_id: str,
    readings: dict,  # e.g. {"temperature": 92.0, "vibration": 3.8}
) -> List[Alert]:
    """Evaluate telemetry readings against threshold rules and create alerts."""
    new_alerts: List[Alert] = []
    for rule in _THRESHOLD_RULES:
        metric = rule["metric"]
        value = readings.get(metric)
        if value is None:
            continue
        inverted = rule.get("inverted", False)
        triggered = (value < rule["threshold"]) if inverted else (value > rule["threshold"])
        if triggered:
            ac = AlertCreate(
                company_id=company_id,
                asset_id=asset_id,
                severity=rule["severity"],
                category=rule["category"],
                title=rule["title"],
                metric_name=metric,
                metric_value=value,
                threshold=rule["threshold"],
                source="threshold_engine",
            )
            alert = await create_alert(db, ac)
            new_alerts.append(alert)
    return new_alerts


async def get_alert(db: AsyncSession, alert_id: str) -> Optional[Alert]:
    result = await db.execute(select(Alert).where(Alert.id == alert_id))
    return result.scalar_one_or_none()


async def list_alerts(
    db: AsyncSession,
    company_id: Optional[str] = None,
    severity: Optional[AlertSeverity] = None,
    status: Optional[AlertStatus] = None,
    asset_id: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> List[Alert]:
    q = select(Alert)
    if company_id:
        q = q.where(Alert.company_id == company_id)
    if severity:
        q = q.where(Alert.severity == severity)
    if status:
        q = q.where(Alert.status == status)
    if asset_id:
        q = q.where(Alert.asset_id == asset_id)
    q = q.order_by(Alert.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(q)
    return list(result.scalars().all())


async def update_alert(
    db: AsyncSession, alert_id: str, data: AlertUpdate, user_id: Optional[str] = None
) -> Optional[Alert]:
    alert = await get_alert(db, alert_id)
    if alert is None:
        return None
    changes = data.model_dump(exclude_unset=True)
    new_status = changes.get("status")
    if new_status == AlertStatus.ACK:
        changes["acknowledged_by"] = user_id
        changes["acknowledged_at"] = datetime.now(tz=timezone.utc)
    if new_status in (AlertStatus.RESOLVED, AlertStatus.AUTO_RESOLVED):
        changes["resolved_at"] = datetime.now(tz=timezone.utc)
    for key, value in changes.items():
        setattr(alert, key, value)
    alert.updated_at = datetime.now(tz=timezone.utc)
    await db.flush()
    return alert
