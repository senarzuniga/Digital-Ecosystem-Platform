"""
Tests for CMMS service and router.
"""

import pytest
import pytest_asyncio

from backend.models.work_order import WOPriority, WOStatus, WOType, WorkOrderCreate
from backend.services import cmms_service
from backend.tests.conftest import AUTH_ADMIN, AUTH_MANAGER, AUTH_TECH


# ── Unit tests (service layer) ─────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_create_work_order(db):
    data = WorkOrderCreate(
        company_id="ACME",
        title="Test work order",
        wo_type=WOType.CORRECTIVE,
        priority=WOPriority.HIGH,
    )
    wo = await cmms_service.create_work_order(db, data, created_by="test-user")
    assert wo.id is not None
    assert wo.wo_number.startswith("WO-")
    assert wo.status == WOStatus.OPEN
    assert wo.priority == WOPriority.HIGH


@pytest.mark.asyncio
async def test_create_work_order_with_assignee(db):
    data = WorkOrderCreate(
        company_id="ACME",
        title="Assigned WO",
        assigned_to="technician-1",
        priority=WOPriority.MEDIUM,
    )
    wo = await cmms_service.create_work_order(db, data)
    assert wo.status == WOStatus.ASSIGNED


@pytest.mark.asyncio
async def test_update_work_order_close(db):
    data = WorkOrderCreate(company_id="ACME", title="To be closed")
    wo = await cmms_service.create_work_order(db, data)

    from backend.models.work_order import WorkOrderUpdate
    updated = await cmms_service.update_work_order(
        db, wo.id, WorkOrderUpdate(status=WOStatus.CLOSED, actual_cost=50000)
    )
    assert updated.status == WOStatus.CLOSED
    assert updated.closed_at is not None
    assert updated.actual_cost == 50000


@pytest.mark.asyncio
async def test_add_spare_part(db):
    data = WorkOrderCreate(company_id="ACME", title="Spare part test")
    wo = await cmms_service.create_work_order(db, data)

    from backend.models.work_order import SparePartIn
    sp = await cmms_service.add_spare_part(
        db, wo.id, SparePartIn(sku="BRG-001", description="Deep groove ball bearing", quantity=2, unit_cost=2500)
    )
    assert sp is not None
    assert sp.sku == "BRG-001"


@pytest.mark.asyncio
async def test_add_comment(db):
    data = WorkOrderCreate(company_id="ACME", title="Comment test")
    wo = await cmms_service.create_work_order(db, data)

    from backend.models.work_order import CommentIn
    c = await cmms_service.add_comment(
        db, wo.id, CommentIn(author_name="Jane Tech", body="Inspected — replacing bearings")
    )
    assert c is not None
    assert c.body == "Inspected — replacing bearings"


@pytest.mark.asyncio
async def test_list_work_orders_filter(db):
    for i in range(3):
        await cmms_service.create_work_order(
            db, WorkOrderCreate(company_id="ACME-FILTER", title=f"WO {i}", priority=WOPriority.LOW)
        )

    orders = await cmms_service.list_work_orders(db, company_id="ACME-FILTER")
    assert len(orders) >= 3


@pytest.mark.asyncio
async def test_get_nonexistent_work_order(db):
    wo = await cmms_service.get_work_order(db, "nonexistent-id")
    assert wo is None


@pytest.mark.asyncio
async def test_technician_workload(db):
    tech_id = "tech-workload-01"
    for i in range(2):
        await cmms_service.create_work_order(
            db, WorkOrderCreate(company_id="ACME", title=f"Workload WO {i}", assigned_to=tech_id)
        )
    result = await cmms_service.get_technician_workload(db, tech_id)
    assert result["technician_id"] == tech_id
    assert result["total_open"] >= 2


# ── Integration tests (HTTP API) ──────────────────────────────────────────────
@pytest.mark.asyncio
async def test_api_create_work_order(client):
    response = await client.post(
        "/api/v1/cmms/work-orders",
        json={
            "company_id": "ACME",
            "title":      "API Work Order",
            "wo_type":    "corrective",
            "priority":   "medium",
        },
        headers=AUTH_TECH,
    )
    assert response.status_code == 201
    body = response.json()
    assert body["wo_number"].startswith("WO-")
    assert body["status"] == "open"


@pytest.mark.asyncio
async def test_api_list_work_orders(client):
    response = await client.get(
        "/api/v1/cmms/work-orders?company_id=ACME",
        headers=AUTH_TECH,
    )
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_api_update_work_order(client):
    create_resp = await client.post(
        "/api/v1/cmms/work-orders",
        json={"company_id": "ACME", "title": "Update test WO"},
        headers=AUTH_TECH,
    )
    wo_id = create_resp.json()["id"]

    update_resp = await client.patch(
        f"/api/v1/cmms/work-orders/{wo_id}",
        json={"status": "in_progress"},
        headers=AUTH_TECH,
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["status"] == "in_progress"


@pytest.mark.asyncio
async def test_api_sla_breached_requires_manager(client):
    response = await client.get(
        "/api/v1/cmms/sla-breached",
        headers=AUTH_TECH,
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_api_sla_breached_manager(client):
    response = await client.get(
        "/api/v1/cmms/sla-breached",
        headers=AUTH_MANAGER,
    )
    assert response.status_code == 200
