"""
Data router — assets and telemetry.
"""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from backend.core.security import get_current_user_payload
from backend.models.asset import AssetCreate, AssetOut, AssetUpdate, TelemetryCreate, TelemetryOut
from backend.services import data_service

router = APIRouter(prefix="/data", tags=["Data"])


@router.post("/assets", response_model=AssetOut, status_code=201)
async def create_asset(
    data: AssetCreate,
    _auth: dict = Depends(get_current_user_payload),
    db: AsyncSession = Depends(get_db),
):
    asset = await data_service.create_asset(db, data)
    return AssetOut.model_validate(asset)


@router.get("/assets", response_model=List[AssetOut])
async def list_assets(
    company_id:  Optional[str] = Query(None),
    active_only: bool = Query(True),
    limit:  int = Query(200, ge=1, le=500),
    offset: int = Query(0, ge=0),
    _auth: dict = Depends(get_current_user_payload),
    db: AsyncSession = Depends(get_db),
):
    assets = await data_service.list_assets(db, company_id=company_id, active_only=active_only, limit=limit, offset=offset)
    return [AssetOut.model_validate(a) for a in assets]


@router.get("/assets/{asset_id}", response_model=AssetOut)
async def get_asset(
    asset_id: str,
    _auth: dict = Depends(get_current_user_payload),
    db: AsyncSession = Depends(get_db),
):
    asset = await data_service.get_asset(db, asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    return AssetOut.model_validate(asset)


@router.patch("/assets/{asset_id}", response_model=AssetOut)
async def update_asset(
    asset_id: str,
    data: AssetUpdate,
    _auth: dict = Depends(get_current_user_payload),
    db: AsyncSession = Depends(get_db),
):
    asset = await data_service.update_asset(db, asset_id, data)
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    return AssetOut.model_validate(asset)


@router.post("/telemetry", response_model=TelemetryOut, status_code=201)
async def ingest_telemetry(
    data: TelemetryCreate,
    _auth: dict = Depends(get_current_user_payload),
    db: AsyncSession = Depends(get_db),
):
    reading = await data_service.ingest_telemetry(db, data)
    return TelemetryOut.model_validate(reading)


@router.get("/telemetry/{asset_id}", response_model=List[TelemetryOut])
async def get_telemetry(
    asset_id: str,
    limit: int = Query(96, ge=1, le=1000),
    _auth: dict = Depends(get_current_user_payload),
    db: AsyncSession = Depends(get_db),
):
    readings = await data_service.get_telemetry(db, asset_id=asset_id, limit=limit)
    return [TelemetryOut.model_validate(r) for r in readings]
