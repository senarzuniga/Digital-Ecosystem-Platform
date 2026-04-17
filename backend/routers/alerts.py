"""
Alerts router.
"""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from backend.core.security import get_current_user_payload
from backend.models.alert import AlertCreate, AlertOut, AlertSeverity, AlertStatus, AlertUpdate
from backend.services import alert_service

router = APIRouter(prefix="/alerts", tags=["Alerts"])


@router.post("/", response_model=AlertOut, status_code=201)
async def create_alert(
    data: AlertCreate,
    _auth: dict = Depends(get_current_user_payload),
    db: AsyncSession = Depends(get_db),
):
    alert = await alert_service.create_alert(db, data)
    return AlertOut.model_validate(alert)


@router.get("/", response_model=List[AlertOut])
async def list_alerts(
    company_id: Optional[str]    = Query(None),
    severity:   Optional[AlertSeverity] = Query(None),
    status:     Optional[AlertStatus]   = Query(None),
    asset_id:   Optional[str]    = Query(None),
    limit:  int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    _auth: dict = Depends(get_current_user_payload),
    db: AsyncSession = Depends(get_db),
):
    alerts = await alert_service.list_alerts(
        db, company_id=company_id, severity=severity,
        status=status, asset_id=asset_id, limit=limit, offset=offset,
    )
    return [AlertOut.model_validate(a) for a in alerts]


@router.get("/{alert_id}", response_model=AlertOut)
async def get_alert(
    alert_id: str,
    _auth: dict = Depends(get_current_user_payload),
    db: AsyncSession = Depends(get_db),
):
    alert = await alert_service.get_alert(db, alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    return AlertOut.model_validate(alert)


@router.patch("/{alert_id}", response_model=AlertOut)
async def update_alert(
    alert_id: str,
    data: AlertUpdate,
    payload: dict = Depends(get_current_user_payload),
    db: AsyncSession = Depends(get_db),
):
    alert = await alert_service.update_alert(db, alert_id, data, user_id=payload.get("sub"))
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    return AlertOut.model_validate(alert)
