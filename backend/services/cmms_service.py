"""
CMMS Service — Work Order CRUD, lifecycle management, SLA tracking,
technician assignment, spare parts, and comments.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.core.events import Topics, get_event_bus
from backend.models.work_order import (
    WOComment,
    WOPriority,
    WOSparePart,
    WOStatus,
    WOType,
    WorkOrder,
    WorkOrderCreate,
    WorkOrderOut,
    WorkOrderUpdate,
    CommentIn,
    SparePartIn,
)

logger = logging.getLogger(__name__)

# ── Counter for WO numbers (per instance; use sequence in prod) ────────────────
_wo_counter: int = 1000


def _next_wo_number() -> str:
    global _wo_counter
    _wo_counter += 1
    return f"WO-{_wo_counter:06d}"


async def create_work_order(
    db: AsyncSession, data: WorkOrderCreate, created_by: Optional[str] = None
) -> WorkOrder:
    wo = WorkOrder(
        wo_number=_next_wo_number(),
        company_id=data.company_id,
        asset_id=data.asset_id,
        title=data.title,
        description=data.description,
        wo_type=data.wo_type,
        priority=data.priority,
        assigned_to=data.assigned_to,
        due_date=data.due_date,
        sla_hours=data.sla_hours,
        estimated_cost=data.estimated_cost,
        alert_id=data.alert_id,
        created_by=created_by,
        status=WOStatus.OPEN if data.assigned_to is None else WOStatus.ASSIGNED,
    )
    db.add(wo)
    await db.flush()

    # Publish event
    bus = get_event_bus()
    await bus.publish(
        Topics.WORK_ORDER_CREATED,
        {
            "work_order_id": wo.id,
            "wo_number": wo.wo_number,
            "company_id": wo.company_id,
            "asset_id": wo.asset_id,
            "priority": wo.priority.value,
            "title": wo.title,
        },
        source="cmms",
    )

    logger.info("Created work order %s for company %s", wo.wo_number, wo.company_id)
    return wo


async def get_work_order(db: AsyncSession, wo_id: str) -> Optional[WorkOrder]:
    result = await db.execute(
        select(WorkOrder)
        .options(selectinload(WorkOrder.spare_parts), selectinload(WorkOrder.comments))
        .where(WorkOrder.id == wo_id)
    )
    return result.scalar_one_or_none()


async def list_work_orders(
    db: AsyncSession,
    company_id: Optional[str] = None,
    status: Optional[WOStatus] = None,
    priority: Optional[WOPriority] = None,
    asset_id: Optional[str] = None,
    assigned_to: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> List[WorkOrder]:
    q = select(WorkOrder).options(
        selectinload(WorkOrder.spare_parts),
        selectinload(WorkOrder.comments),
    )
    if company_id:
        q = q.where(WorkOrder.company_id == company_id)
    if status:
        q = q.where(WorkOrder.status == status)
    if priority:
        q = q.where(WorkOrder.priority == priority)
    if asset_id:
        q = q.where(WorkOrder.asset_id == asset_id)
    if assigned_to:
        q = q.where(WorkOrder.assigned_to == assigned_to)
    q = q.order_by(WorkOrder.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(q)
    return list(result.scalars().all())


async def update_work_order(
    db: AsyncSession, wo_id: str, data: WorkOrderUpdate
) -> Optional[WorkOrder]:
    wo = await get_work_order(db, wo_id)
    if wo is None:
        return None

    changes = data.model_dump(exclude_unset=True)

    # Handle lifecycle transitions
    new_status = changes.get("status")
    if new_status == WOStatus.CLOSED and wo.closed_at is None:
        changes["closed_at"] = datetime.now(tz=timezone.utc)
    if new_status == WOStatus.ASSIGNED and "assigned_to" not in changes:
        pass  # status changed without new assignee — OK

    for key, value in changes.items():
        setattr(wo, key, value)

    wo.updated_at = datetime.now(tz=timezone.utc)
    await db.flush()

    bus = get_event_bus()
    await bus.publish(
        Topics.WORK_ORDER_UPDATED,
        {"work_order_id": wo_id, "changes": list(changes.keys()), "new_status": new_status},
        source="cmms",
    )

    return wo


async def add_spare_part(
    db: AsyncSession, wo_id: str, part: SparePartIn
) -> Optional[WOSparePart]:
    wo = await get_work_order(db, wo_id)
    if wo is None:
        return None
    sp = WOSparePart(
        work_order_id=wo_id,
        sku=part.sku,
        description=part.description,
        quantity=part.quantity,
        unit_cost=part.unit_cost,
    )
    db.add(sp)
    await db.flush()
    return sp


async def add_comment(
    db: AsyncSession, wo_id: str, comment: CommentIn
) -> Optional[WOComment]:
    wo = await get_work_order(db, wo_id)
    if wo is None:
        return None
    c = WOComment(
        work_order_id=wo_id,
        author_name=comment.author_name,
        body=comment.body,
        user_id=comment.user_id,
    )
    db.add(c)
    await db.flush()
    return c


# ── SLA Tracking ───────────────────────────────────────────────────────────────
async def get_sla_breached_orders(
    db: AsyncSession, company_id: Optional[str] = None
) -> List[WorkOrder]:
    """Return open work orders where SLA has been breached."""
    now = datetime.now(tz=timezone.utc)
    q = select(WorkOrder).where(
        WorkOrder.status.notin_([WOStatus.CLOSED, WOStatus.CANCELLED]),
        WorkOrder.due_date.is_not(None),
        WorkOrder.due_date < now,
    )
    if company_id:
        q = q.where(WorkOrder.company_id == company_id)
    result = await db.execute(q)
    return list(result.scalars().all())


async def get_technician_workload(
    db: AsyncSession, technician_id: str
) -> dict:
    """Return open/in-progress WO counts for a technician."""
    q = select(WorkOrder).where(
        WorkOrder.assigned_to == technician_id,
        WorkOrder.status.notin_([WOStatus.CLOSED, WOStatus.CANCELLED]),
    )
    result = await db.execute(q)
    orders = list(result.scalars().all())
    return {
        "technician_id": technician_id,
        "total_open": len(orders),
        "by_priority": {
            p.value: sum(1 for o in orders if o.priority == p)
            for p in WOPriority
        },
    }
