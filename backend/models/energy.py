"""
SQLAlchemy ORM models + Pydantic schemas for Energy readings and targets.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from pydantic import BaseModel, ConfigDict
from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.core.database import Base


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


class EnergyReading(Base):
    __tablename__ = "energy_readings"

    id:          Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    asset_id:    Mapped[str] = mapped_column(String(36), ForeignKey("assets.id", ondelete="CASCADE"), index=True)
    company_id:  Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    timestamp:   Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)
    kwh:         Mapped[float] = mapped_column(Float, nullable=False)
    kw_peak:     Mapped[Optional[float]] = mapped_column(Float)
    co2_kg:      Mapped[Optional[float]] = mapped_column(Float)
    cost_cents:  Mapped[Optional[int]]   = mapped_column(Integer)

    asset: Mapped["Asset"] = relationship("Asset", back_populates="energy_readings", lazy="select")


class EnergyTarget(Base):
    __tablename__ = "energy_targets"

    id:          Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    company_id:  Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    asset_id:    Mapped[Optional[str]] = mapped_column(String(36))
    period:      Mapped[str] = mapped_column(String(8))   # "2026-04" (YYYY-MM)
    target_kwh:  Mapped[float] = mapped_column(Float)
    target_co2:  Mapped[Optional[float]] = mapped_column(Float)
    created_at:  Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class EnergyOptimizationRecommendation(Base):
    __tablename__ = "energy_recommendations"

    id:          Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    company_id:  Mapped[str] = mapped_column(String(64), index=True)
    asset_id:    Mapped[Optional[str]] = mapped_column(String(36))
    title:       Mapped[str] = mapped_column(String(256))
    description: Mapped[Optional[str]] = mapped_column(Text)
    potential_saving_kwh: Mapped[Optional[float]] = mapped_column(Float)
    potential_saving_pct: Mapped[Optional[float]] = mapped_column(Float)
    is_applied:  Mapped[bool] = mapped_column(default=False)
    created_at:  Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


# ── Pydantic schemas ───────────────────────────────────────────────────────────
class EnergyReadingCreate(BaseModel):
    asset_id:   str
    company_id: str
    kwh:        float
    kw_peak:    Optional[float] = None
    co2_kg:     Optional[float] = None
    cost_cents: Optional[int] = None


class EnergyReadingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id:         int
    asset_id:   str
    company_id: str
    timestamp:  datetime
    kwh:        float
    kw_peak:    Optional[float]
    co2_kg:     Optional[float]
    cost_cents: Optional[int]


class EnergySummary(BaseModel):
    company_id:      str
    period:          str
    total_kwh:       float
    total_co2_kg:    float
    total_cost_cents: int
    asset_count:     int
    avg_kwh_per_asset: float
    yoy_change_pct:  Optional[float] = None


class EnergyRecommendationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id:                     str
    asset_id:               Optional[str]
    title:                  str
    description:            Optional[str]
    potential_saving_kwh:   Optional[float]
    potential_saving_pct:   Optional[float]
    is_applied:             bool
    created_at:             datetime
