"""
Tests for Alert service and router.
"""

import pytest

from backend.models.alert import AlertCategory, AlertCreate, AlertSeverity, AlertStatus, AlertUpdate
from backend.services import alert_service
from backend.tests.conftest import AUTH_ADMIN, AUTH_TECH


@pytest.mark.asyncio
async def test_create_alert_basic(db):
    data = AlertCreate(
        company_id="ACME",
        severity=AlertSeverity.WARNING,
        category=AlertCategory.OPERATIONAL,
        title="High temperature",
        metric_name="temperature",
        metric_value=82.0,
        threshold=75.0,
        source="test",
    )
    alert = await alert_service.create_alert(db, data, auto_respond=False)
    assert alert.id is not None
    assert alert.status == AlertStatus.OPEN
    assert alert.root_cause is not None  # auto-enriched


@pytest.mark.asyncio
async def test_create_critical_alert_auto_creates_wo(db):
    data = AlertCreate(
        company_id="ACME-AUTO",
        severity=AlertSeverity.CRITICAL,
        category=AlertCategory.MAINTENANCE,
        title="Critical vibration",
        metric_name="vibration",
        metric_value=5.2,
        threshold=4.0,
    )
    alert = await alert_service.create_alert(db, data, auto_respond=True)
    assert alert.work_order_id is not None
    assert alert.auto_actioned is True


@pytest.mark.asyncio
async def test_acknowledge_alert(db):
    data = AlertCreate(
        company_id="ACME",
        severity=AlertSeverity.WARNING,
        category=AlertCategory.OPERATIONAL,
        title="Test ack",
    )
    alert = await alert_service.create_alert(db, data, auto_respond=False)
    updated = await alert_service.update_alert(
        db, alert.id, AlertUpdate(status=AlertStatus.ACK), user_id="user-001"
    )
    assert updated.status == AlertStatus.ACK
    assert updated.acknowledged_by == "user-001"
    assert updated.acknowledged_at is not None


@pytest.mark.asyncio
async def test_threshold_check_triggers_alerts(db):
    alerts = await alert_service.check_telemetry_thresholds(
        db,
        company_id="ACME",
        asset_id="machine-001",
        readings={"temperature": 90.0, "vibration": 4.5},
    )
    assert len(alerts) >= 2  # both temperature and vibration rules should fire


@pytest.mark.asyncio
async def test_threshold_check_below_threshold(db):
    alerts = await alert_service.check_telemetry_thresholds(
        db,
        company_id="ACME",
        asset_id="machine-002",
        readings={"temperature": 50.0, "vibration": 1.0},
    )
    assert len(alerts) == 0


@pytest.mark.asyncio
async def test_list_alerts_filter(db):
    for _ in range(3):
        await alert_service.create_alert(
            db,
            AlertCreate(company_id="LIST-CO", severity=AlertSeverity.INFO, category=AlertCategory.ENERGY, title="Filter test"),
            auto_respond=False,
        )
    alerts = await alert_service.list_alerts(db, company_id="LIST-CO")
    assert len(alerts) >= 3


# ── API ────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_api_create_alert(client):
    resp = await client.post(
        "/api/v1/alerts/",
        json={
            "company_id": "ACME",
            "severity":   "warning",
            "category":   "operational",
            "title":      "API alert test",
        },
        headers=AUTH_TECH,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "open"


@pytest.mark.asyncio
async def test_api_list_alerts(client):
    resp = await client.get("/api/v1/alerts/?company_id=ACME", headers=AUTH_TECH)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_api_get_nonexistent_alert(client):
    resp = await client.get("/api/v1/alerts/does-not-exist", headers=AUTH_TECH)
    assert resp.status_code == 404
