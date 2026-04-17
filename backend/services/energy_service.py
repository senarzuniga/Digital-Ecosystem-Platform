"""
Energy Service — per-machine consumption tracking, plant aggregation,
optimization recommendations, CO₂ reporting.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.events import Topics, get_event_bus
from backend.models.energy import (
    EnergyOptimizationRecommendation,
    EnergyReading,
    EnergyReadingCreate,
    EnergyTarget,
    EnergySummary,
)

logger = logging.getLogger(__name__)

# CO₂ emission factor: kg per kWh (EU average, 2024)
CO2_KG_PER_KWH = 0.233
# Electricity cost: USD cents per kWh
COST_CENTS_PER_KWH = 15


async def record_energy_reading(
    db: AsyncSession, data: EnergyReadingCreate
) -> EnergyReading:
    co2 = data.co2_kg if data.co2_kg is not None else round(data.kwh * CO2_KG_PER_KWH, 4)
    cost = data.cost_cents if data.cost_cents is not None else int(data.kwh * COST_CENTS_PER_KWH)

    reading = EnergyReading(
        asset_id=data.asset_id,
        company_id=data.company_id,
        kwh=data.kwh,
        kw_peak=data.kw_peak,
        co2_kg=co2,
        cost_cents=cost,
    )
    db.add(reading)
    await db.flush()

    # Check against targets and emit event if threshold exceeded
    await _check_energy_threshold(db, data.company_id, data.asset_id, data.kwh)

    return reading


async def _check_energy_threshold(
    db: AsyncSession, company_id: str, asset_id: str, kwh: float
) -> None:
    """Check if a single reading significantly exceeds expectations."""
    # Simple heuristic: flag if single reading > 50 kWh (configurable)
    threshold_kwh = 50.0
    if kwh > threshold_kwh:
        bus = get_event_bus()
        await bus.publish(
            Topics.ENERGY_THRESHOLD_EXCEEDED,
            {
                "company_id":  company_id,
                "asset_id":    asset_id,
                "current_kwh": kwh,
                "target_kwh":  threshold_kwh,
            },
            source="energy_service",
        )


async def get_energy_summary(
    db: AsyncSession,
    company_id: str,
    period: Optional[str] = None,  # "YYYY-MM"
) -> EnergySummary:
    q = select(
        func.sum(EnergyReading.kwh).label("total_kwh"),
        func.sum(EnergyReading.co2_kg).label("total_co2"),
        func.sum(EnergyReading.cost_cents).label("total_cost"),
        func.count(func.distinct(EnergyReading.asset_id)).label("asset_count"),
    ).where(EnergyReading.company_id == company_id)

    if period:
        # e.g. "2026-04" → filter by year-month prefix
        year, month = int(period[:4]), int(period[5:7])
        from datetime import date
        start = datetime(year, month, 1, tzinfo=timezone.utc)
        if month == 12:
            end = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
        else:
            end = datetime(year, month + 1, 1, tzinfo=timezone.utc)
        q = q.where(EnergyReading.timestamp >= start, EnergyReading.timestamp < end)

    result = await db.execute(q)
    row = result.one()
    total_kwh   = float(row.total_kwh or 0)
    total_co2   = float(row.total_co2 or 0)
    total_cost  = int(row.total_cost or 0)
    asset_count = int(row.asset_count or 1)

    return EnergySummary(
        company_id=company_id,
        period=period or "all-time",
        total_kwh=total_kwh,
        total_co2_kg=total_co2,
        total_cost_cents=total_cost,
        asset_count=asset_count,
        avg_kwh_per_asset=total_kwh / max(asset_count, 1),
    )


async def list_readings(
    db: AsyncSession,
    company_id: Optional[str] = None,
    asset_id: Optional[str] = None,
    limit: int = 200,
) -> List[EnergyReading]:
    q = select(EnergyReading)
    if company_id:
        q = q.where(EnergyReading.company_id == company_id)
    if asset_id:
        q = q.where(EnergyReading.asset_id == asset_id)
    q = q.order_by(EnergyReading.timestamp.desc()).limit(limit)
    result = await db.execute(q)
    return list(result.scalars().all())


async def get_recommendations(
    db: AsyncSession, company_id: str, asset_id: Optional[str] = None
) -> List[EnergyOptimizationRecommendation]:
    q = select(EnergyOptimizationRecommendation).where(
        EnergyOptimizationRecommendation.company_id == company_id
    )
    if asset_id:
        q = q.where(EnergyOptimizationRecommendation.asset_id == asset_id)
    q = q.order_by(EnergyOptimizationRecommendation.created_at.desc())
    result = await db.execute(q)
    return list(result.scalars().all())


async def generate_recommendations(
    db: AsyncSession, company_id: str
) -> List[EnergyOptimizationRecommendation]:
    """Rule-based recommendation generation.  ML-based: plug in model here."""
    summary = await get_energy_summary(db, company_id)
    recs: List[EnergyOptimizationRecommendation] = []

    if summary.avg_kwh_per_asset > 30:
        rec = EnergyOptimizationRecommendation(
            company_id=company_id,
            title="Shift high-load machines to off-peak hours",
            description=(
                f"Average consumption is {summary.avg_kwh_per_asset:.1f} kWh/machine. "
                "Shifting 30% of load to off-peak (22:00–06:00) could reduce peak demand charges by ~20%."
            ),
            potential_saving_pct=20.0,
            potential_saving_kwh=summary.total_kwh * 0.20,
        )
        db.add(rec)
        recs.append(rec)

    if summary.total_co2_kg > 500:
        rec2 = EnergyOptimizationRecommendation(
            company_id=company_id,
            title="CO₂ reduction: consider renewable energy sourcing",
            description=(
                f"Total CO₂ footprint: {summary.total_co2_kg:.1f} kg. "
                "Switching to renewable energy tariff or on-site solar could achieve net-zero."
            ),
            potential_saving_pct=100.0,
            potential_saving_kwh=0,
        )
        db.add(rec2)
        recs.append(rec2)

    await db.flush()
    logger.info("Generated %d energy recommendations for company %s", len(recs), company_id)
    return recs
