"""
Data Service — Asset CRUD + telemetry ingestion.
"""

from __future__ import annotations

import logging
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.asset import (
    Asset,
    AssetCreate,
    AssetUpdate,
    MachineTelemetry,
    TelemetryCreate,
)
from backend.services.alert_service import check_telemetry_thresholds

logger = logging.getLogger(__name__)


async def create_asset(db: AsyncSession, data: AssetCreate) -> Asset:
    asset = Asset(**data.model_dump())
    db.add(asset)
    await db.flush()
    logger.info("Asset created: %s (%s)", asset.name, asset.id)
    return asset


async def get_asset(db: AsyncSession, asset_id: str) -> Optional[Asset]:
    result = await db.execute(select(Asset).where(Asset.id == asset_id))
    return result.scalar_one_or_none()


async def list_assets(
    db: AsyncSession,
    company_id: Optional[str] = None,
    active_only: bool = True,
    limit: int = 200,
    offset: int = 0,
) -> List[Asset]:
    q = select(Asset)
    if company_id:
        q = q.where(Asset.company_id == company_id)
    if active_only:
        q = q.where(Asset.is_active.is_(True))
    q = q.order_by(Asset.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(q)
    return list(result.scalars().all())


async def update_asset(db: AsyncSession, asset_id: str, data: AssetUpdate) -> Optional[Asset]:
    asset = await get_asset(db, asset_id)
    if asset is None:
        return None
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(asset, key, value)
    await db.flush()
    return asset


async def ingest_telemetry(
    db: AsyncSession, data: TelemetryCreate
) -> MachineTelemetry:
    reading = MachineTelemetry(**data.model_dump())
    db.add(reading)
    await db.flush()

    # Evaluate thresholds and raise alerts if needed
    await check_telemetry_thresholds(
        db,
        company_id=(await get_asset(db, data.asset_id)).company_id,
        asset_id=data.asset_id,
        readings={
            "temperature": data.temperature,
            "vibration":   data.vibration,
            "power_kw":    data.power_kw,
            "oee":         data.oee,
        },
    )
    return reading


async def get_telemetry(
    db: AsyncSession,
    asset_id: str,
    limit: int = 96,
) -> List[MachineTelemetry]:
    q = (
        select(MachineTelemetry)
        .where(MachineTelemetry.asset_id == asset_id)
        .order_by(MachineTelemetry.timestamp.desc())
        .limit(limit)
    )
    result = await db.execute(q)
    return list(reversed(result.scalars().all()))
