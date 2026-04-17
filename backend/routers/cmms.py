"""
CMMS router — Work Orders, spare parts, comments, SLA.
"""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from backend.core.security import Role, get_current_user_payload, require_roles
from backend.models.work_order import (
    CommentIn,
    CommentOut,
    SparePartIn,
    SparePartOut,
    WOPriority,
    WOStatus,
    WorkOrderCreate,
    WorkOrderOut,
    WorkOrderUpdate,
)
from backend.services import cmms_service

router = APIRouter(prefix="/cmms", tags=["CMMS"])


@router.post("/work-orders", response_model=WorkOrderOut, status_code=status.HTTP_201_CREATED)
async def create_work_order(
    data: WorkOrderCreate,
    payload: dict = Depends(get_current_user_payload),
    db: AsyncSession = Depends(get_db),
):
    wo = await cmms_service.create_work_order(db, data, created_by=payload.get("sub"))
    # Re-fetch with eager-loaded relationships for serialisation
    wo = await cmms_service.get_work_order(db, wo.id)
    return WorkOrderOut.model_validate(wo)


@router.get("/work-orders", response_model=List[WorkOrderOut])
async def list_work_orders(
    company_id: Optional[str] = Query(None),
    status:     Optional[WOStatus]   = Query(None),
    priority:   Optional[WOPriority] = Query(None),
    asset_id:   Optional[str] = Query(None),
    assigned_to: Optional[str] = Query(None),
    limit:  int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    _auth: dict = Depends(get_current_user_payload),
    db: AsyncSession = Depends(get_db),
):
    orders = await cmms_service.list_work_orders(
        db,
        company_id=company_id,
        status=status,
        priority=priority,
        asset_id=asset_id,
        assigned_to=assigned_to,
        limit=limit,
        offset=offset,
    )
    return [WorkOrderOut.model_validate(o) for o in orders]


@router.get("/work-orders/{wo_id}", response_model=WorkOrderOut)
async def get_work_order(
    wo_id: str,
    _auth: dict = Depends(get_current_user_payload),
    db: AsyncSession = Depends(get_db),
):
    wo = await cmms_service.get_work_order(db, wo_id)
    if wo is None:
        raise HTTPException(status_code=404, detail="Work order not found")
    return WorkOrderOut.model_validate(wo)


@router.patch("/work-orders/{wo_id}", response_model=WorkOrderOut)
async def update_work_order(
    wo_id: str,
    data: WorkOrderUpdate,
    _auth: dict = Depends(get_current_user_payload),
    db: AsyncSession = Depends(get_db),
):
    wo = await cmms_service.update_work_order(db, wo_id, data)
    if wo is None:
        raise HTTPException(status_code=404, detail="Work order not found")
    # Re-fetch with eager-loaded relationships for serialisation
    wo = await cmms_service.get_work_order(db, wo_id)
    return WorkOrderOut.model_validate(wo)


@router.post("/work-orders/{wo_id}/parts", response_model=SparePartOut, status_code=status.HTTP_201_CREATED)
async def add_spare_part(
    wo_id: str,
    data: SparePartIn,
    _auth: dict = Depends(get_current_user_payload),
    db: AsyncSession = Depends(get_db),
):
    sp = await cmms_service.add_spare_part(db, wo_id, data)
    if sp is None:
        raise HTTPException(status_code=404, detail="Work order not found")
    return SparePartOut.model_validate(sp)


@router.post("/work-orders/{wo_id}/comments", response_model=CommentOut, status_code=status.HTTP_201_CREATED)
async def add_comment(
    wo_id: str,
    data: CommentIn,
    _auth: dict = Depends(get_current_user_payload),
    db: AsyncSession = Depends(get_db),
):
    comment = await cmms_service.add_comment(db, wo_id, data)
    if comment is None:
        raise HTTPException(status_code=404, detail="Work order not found")
    return CommentOut.model_validate(comment)


@router.get("/sla-breached", response_model=List[WorkOrderOut])
async def sla_breached(
    company_id: Optional[str] = Query(None),
    _auth: dict = Depends(require_roles(Role.ADMIN, Role.MANAGER)),
    db: AsyncSession = Depends(get_db),
):
    orders = await cmms_service.get_sla_breached_orders(db, company_id=company_id)
    return [WorkOrderOut.model_validate(o) for o in orders]


@router.get("/technician/{technician_id}/workload")
async def technician_workload(
    technician_id: str,
    _auth: dict = Depends(get_current_user_payload),
    db: AsyncSession = Depends(get_db),
):
    return await cmms_service.get_technician_workload(db, technician_id)
