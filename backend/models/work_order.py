"""
SQLAlchemy ORM models + Pydantic schemas for Work Orders (CMMS).
"""

from __future__ import annotations

import enum
from datetime import datetime, timezone
from typing import List, Optional
from uuid import uuid4

from pydantic import BaseModel, ConfigDict
from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.core.database import Base


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


# ── Enums ──────────────────────────────────────────────────────────────────────
class WOStatus(str, enum.Enum):
    OPEN        = "open"
    ASSIGNED    = "assigned"
    IN_PROGRESS = "in_progress"
    ON_HOLD     = "on_hold"
    CLOSED      = "closed"
    CANCELLED   = "cancelled"


class WOPriority(str, enum.Enum):
    CRITICAL = "critical"
    HIGH     = "high"
    MEDIUM   = "medium"
    LOW      = "low"


class WOType(str, enum.Enum):
    CORRECTIVE   = "corrective"
    PREVENTIVE   = "preventive"
    PREDICTIVE   = "predictive"
    INSPECTION   = "inspection"
    UPGRADE      = "upgrade"


# ── ORM Models ────────────────────────────────────────────────────────────────
class WorkOrder(Base):
    __tablename__ = "work_orders"

    id:           Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    wo_number:    Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    company_id:   Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    asset_id:     Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("assets.id", ondelete="SET NULL"))
    title:        Mapped[str] = mapped_column(String(256), nullable=False)
    description:  Mapped[Optional[str]] = mapped_column(Text)
    wo_type:      Mapped[WOType] = mapped_column(Enum(WOType), default=WOType.CORRECTIVE)
    status:       Mapped[WOStatus] = mapped_column(Enum(WOStatus), default=WOStatus.OPEN, index=True)
    priority:     Mapped[WOPriority] = mapped_column(Enum(WOPriority), default=WOPriority.MEDIUM)
    assigned_to:  Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"))
    created_by:   Mapped[Optional[str]] = mapped_column(String(36))
    alert_id:     Mapped[Optional[str]] = mapped_column(String(36))  # FK to alert that triggered this WO
    due_date:     Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    closed_at:    Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    sla_hours:    Mapped[Optional[int]] = mapped_column(Integer)
    estimated_cost: Mapped[Optional[int]] = mapped_column(Integer)  # cents
    actual_cost:    Mapped[Optional[int]] = mapped_column(Integer)  # cents
    notes:        Mapped[Optional[str]] = mapped_column(Text)
    created_at:   Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at:   Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    asset:  Mapped[Optional["Asset"]]     = relationship("Asset",  back_populates="work_orders", lazy="select")
    technician: Mapped[Optional["User"]]  = relationship("User",   foreign_keys=[assigned_to],  lazy="select")
    spare_parts: Mapped[List["WOSparePart"]] = relationship("WOSparePart", back_populates="work_order", lazy="select")
    comments:    Mapped[List["WOComment"]]   = relationship("WOComment",   back_populates="work_order", lazy="select")


class WOSparePart(Base):
    __tablename__ = "wo_spare_parts"

    id:           Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    work_order_id: Mapped[str] = mapped_column(String(36), ForeignKey("work_orders.id", ondelete="CASCADE"))
    sku:          Mapped[str] = mapped_column(String(64))
    description:  Mapped[str] = mapped_column(String(256))
    quantity:     Mapped[int] = mapped_column(Integer, default=1)
    unit_cost:    Mapped[Optional[int]] = mapped_column(Integer)  # cents

    work_order: Mapped["WorkOrder"] = relationship("WorkOrder", back_populates="spare_parts")


class WOComment(Base):
    __tablename__ = "wo_comments"

    id:           Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    work_order_id: Mapped[str] = mapped_column(String(36), ForeignKey("work_orders.id", ondelete="CASCADE"))
    user_id:      Mapped[Optional[str]] = mapped_column(String(36))
    author_name:  Mapped[str] = mapped_column(String(128))
    body:         Mapped[str] = mapped_column(Text)
    created_at:   Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    work_order: Mapped["WorkOrder"] = relationship("WorkOrder", back_populates="comments")


# ── Pydantic schemas ───────────────────────────────────────────────────────────
class WorkOrderCreate(BaseModel):
    company_id:   str
    asset_id:     Optional[str] = None
    title:        str
    description:  Optional[str] = None
    wo_type:      WOType = WOType.CORRECTIVE
    priority:     WOPriority = WOPriority.MEDIUM
    assigned_to:  Optional[str] = None
    due_date:     Optional[datetime] = None
    sla_hours:    Optional[int] = None
    estimated_cost: Optional[int] = None
    alert_id:     Optional[str] = None


class WorkOrderUpdate(BaseModel):
    title:          Optional[str] = None
    description:    Optional[str] = None
    status:         Optional[WOStatus] = None
    priority:       Optional[WOPriority] = None
    assigned_to:    Optional[str] = None
    due_date:       Optional[datetime] = None
    actual_cost:    Optional[int] = None
    notes:          Optional[str] = None


class SparePartIn(BaseModel):
    sku:         str
    description: str
    quantity:    int = 1
    unit_cost:   Optional[int] = None


class CommentIn(BaseModel):
    author_name: str
    body:        str
    user_id:     Optional[str] = None


class SparePartOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    sku: str
    description: str
    quantity: int
    unit_cost: Optional[int]


class CommentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    author_name: str
    body: str
    created_at: datetime


class WorkOrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id:           str
    wo_number:    str
    company_id:   str
    asset_id:     Optional[str]
    title:        str
    description:  Optional[str]
    wo_type:      WOType
    status:       WOStatus
    priority:     WOPriority
    assigned_to:  Optional[str]
    created_by:   Optional[str]
    alert_id:     Optional[str]
    due_date:     Optional[datetime]
    closed_at:    Optional[datetime]
    sla_hours:    Optional[int]
    estimated_cost: Optional[int]
    actual_cost:    Optional[int]
    notes:        Optional[str]
    created_at:   datetime
    updated_at:   datetime
    spare_parts:  List[SparePartOut] = []
    comments:     List[CommentOut] = []
