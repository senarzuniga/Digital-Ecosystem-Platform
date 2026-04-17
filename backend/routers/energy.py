"""
Energy router.
"""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from backend.core.security import Role, get_current_user_payload, require_roles
from backend.models.energy import (
    EnergyReadingCreate,
    EnergyReadingOut,
    EnergyRecommendationOut,
    EnergySummary,
)
from backend.services import energy_service

router = APIRouter(prefix="/energy", tags=["Energy"])


@router.post("/readings", response_model=EnergyReadingOut, status_code=201)
async def ingest_reading(
    data: EnergyReadingCreate,
    _auth: dict = Depends(get_current_user_payload),
    db: AsyncSession = Depends(get_db),
):
    reading = await energy_service.record_energy_reading(db, data)
    return EnergyReadingOut.model_validate(reading)


@router.get("/readings", response_model=List[EnergyReadingOut])
async def list_readings(
    company_id: Optional[str] = Query(None),
    asset_id:   Optional[str] = Query(None),
    limit: int = Query(200, ge=1, le=1000),
    _auth: dict = Depends(get_current_user_payload),
    db: AsyncSession = Depends(get_db),
):
    readings = await energy_service.list_readings(db, company_id=company_id, asset_id=asset_id, limit=limit)
    return [EnergyReadingOut.model_validate(r) for r in readings]


@router.get("/summary", response_model=EnergySummary)
async def energy_summary(
    company_id: str = Query(...),
    period:     Optional[str] = Query(None, description="YYYY-MM"),
    _auth: dict = Depends(get_current_user_payload),
    db: AsyncSession = Depends(get_db),
):
    return await energy_service.get_energy_summary(db, company_id=company_id, period=period)


@router.get("/recommendations", response_model=List[EnergyRecommendationOut])
async def get_recommendations(
    company_id: str = Query(...),
    asset_id:   Optional[str] = Query(None),
    _auth: dict = Depends(get_current_user_payload),
    db: AsyncSession = Depends(get_db),
):
    recs = await energy_service.get_recommendations(db, company_id=company_id, asset_id=asset_id)
    return [EnergyRecommendationOut.model_validate(r) for r in recs]


@router.post("/recommendations/generate")
async def generate_recommendations(
    company_id: str = Query(...),
    _auth: dict = Depends(require_roles(Role.ADMIN, Role.MANAGER)),
    db: AsyncSession = Depends(get_db),
):
    recs = await energy_service.generate_recommendations(db, company_id=company_id)
    return [EnergyRecommendationOut.model_validate(r) for r in recs]
