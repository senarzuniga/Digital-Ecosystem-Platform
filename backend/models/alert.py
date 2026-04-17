"""
SQLAlchemy ORM models + Pydantic schemas for Alerts.
"""

from __future__ import annotations

import enum
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from pydantic import BaseModel, ConfigDict
from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.core.database import Base


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


class AlertSeverity(str, enum.Enum):
    CRITICAL   = "critical"
    HIGH       = "high"
    WARNING    = "warning"
    INFO       = "info"


class AlertCategory(str, enum.Enum):
    OPERATIONAL  = "operational"
    MAINTENANCE  = "maintenance"
    ECONOMIC     = "economic"
    ENERGY       = "energy"
    SECURITY     = "security"
    COMMERCIAL   = "commercial"


class AlertStatus(str, enum.Enum):
    OPEN       = "open"
    ACK        = "acknowledged"
    IN_REVIEW  = "in_review"
    RESOLVED   = "resolved"
    AUTO_RESOLVED = "auto_resolved"


class Alert(Base):
    __tablename__ = "alerts"

    id:           Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    company_id:   Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    asset_id:     Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("assets.id", ondelete="SET NULL"))
    severity:     Mapped[AlertSeverity] = mapped_column(Enum(AlertSeverity), default=AlertSeverity.WARNING, index=True)
    category:     Mapped[AlertCategory] = mapped_column(Enum(AlertCategory), default=AlertCategory.OPERATIONAL)
    status:       Mapped[AlertStatus]   = mapped_column(Enum(AlertStatus), default=AlertStatus.OPEN, index=True)
    title:        Mapped[str] = mapped_column(String(256), nullable=False)
    description:  Mapped[Optional[str]] = mapped_column(Text)
    root_cause:   Mapped[Optional[str]] = mapped_column(Text)
    recommended_action: Mapped[Optional[str]] = mapped_column(Text)
    metric_name:  Mapped[Optional[str]] = mapped_column(String(64))
    metric_value: Mapped[Optional[float]] = mapped_column(Float)
    threshold:    Mapped[Optional[float]] = mapped_column(Float)
    source:       Mapped[Optional[str]] = mapped_column(String(64))  # e.g. "mqtt", "agent", "rule"
    auto_actioned: Mapped[bool] = mapped_column(Boolean, default=False)
    work_order_id: Mapped[Optional[str]] = mapped_column(String(36))
    acknowledged_by: Mapped[Optional[str]] = mapped_column(String(36))
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    resolved_at:  Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at:   Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at:   Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    asset: Mapped[Optional["Asset"]] = relationship("Asset", back_populates="alerts", lazy="select")


# ── Pydantic schemas ───────────────────────────────────────────────────────────
class AlertCreate(BaseModel):
    company_id:         str
    asset_id:           Optional[str] = None
    severity:           AlertSeverity = AlertSeverity.WARNING
    category:           AlertCategory = AlertCategory.OPERATIONAL
    title:              str
    description:        Optional[str] = None
    metric_name:        Optional[str] = None
    metric_value:       Optional[float] = None
    threshold:          Optional[float] = None
    source:             Optional[str] = None
    recommended_action: Optional[str] = None


class AlertUpdate(BaseModel):
    status:             Optional[AlertStatus] = None
    root_cause:         Optional[str] = None
    recommended_action: Optional[str] = None
    acknowledged_by:    Optional[str] = None
    work_order_id:      Optional[str] = None


class AlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id:               str
    company_id:       str
    asset_id:         Optional[str]
    severity:         AlertSeverity
    category:         AlertCategory
    status:           AlertStatus
    title:            str
    description:      Optional[str]
    root_cause:       Optional[str]
    recommended_action: Optional[str]
    metric_name:      Optional[str]
    metric_value:     Optional[float]
    threshold:        Optional[float]
    source:           Optional[str]
    auto_actioned:    bool
    work_order_id:    Optional[str]
    acknowledged_by:  Optional[str]
    acknowledged_at:  Optional[datetime]
    resolved_at:      Optional[datetime]
    created_at:       datetime
    updated_at:       datetime
