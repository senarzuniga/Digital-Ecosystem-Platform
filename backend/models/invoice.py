"""
SQLAlchemy ORM models + Pydantic schemas for Financial entities:
  - Contract
  - Invoice
  - InvoiceLineItem
"""

from __future__ import annotations

import enum
from datetime import date, datetime, timezone
from typing import List, Optional
from uuid import uuid4

from pydantic import BaseModel, ConfigDict
from sqlalchemy import Date, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.core.database import Base


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


# ── Enums ──────────────────────────────────────────────────────────────────────
class PricingModel(str, enum.Enum):
    FIXED        = "fixed"
    USAGE_BASED  = "usage_based"
    SUBSCRIPTION = "subscription"
    PERFORMANCE  = "performance_based"


class ContractStatus(str, enum.Enum):
    DRAFT     = "draft"
    ACTIVE    = "active"
    EXPIRING  = "expiring"   # < 30 days
    EXPIRED   = "expired"
    CANCELLED = "cancelled"


class InvoiceStatus(str, enum.Enum):
    DRAFT    = "draft"
    ISSUED   = "issued"
    PAID     = "paid"
    OVERDUE  = "overdue"
    VOID     = "void"


# ── ORM Models ────────────────────────────────────────────────────────────────
class Contract(Base):
    __tablename__ = "contracts"

    id:             Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    company_id:     Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    contract_number: Mapped[str] = mapped_column(String(32), unique=True)
    title:          Mapped[str] = mapped_column(String(256))
    pricing_model:  Mapped[PricingModel] = mapped_column(Enum(PricingModel), default=PricingModel.FIXED)
    status:         Mapped[ContractStatus] = mapped_column(Enum(ContractStatus), default=ContractStatus.DRAFT)
    start_date:     Mapped[Optional[date]] = mapped_column(Date)
    end_date:       Mapped[Optional[date]] = mapped_column(Date)
    value_cents:    Mapped[Optional[int]]  = mapped_column(Integer)   # total contract value
    monthly_fee_cents: Mapped[Optional[int]] = mapped_column(Integer) # recurring fee
    sla_uptime_pct: Mapped[Optional[float]] = mapped_column(Float)
    sla_response_hours: Mapped[Optional[int]] = mapped_column(Integer)
    notes:          Mapped[Optional[str]] = mapped_column(Text)
    created_at:     Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at:     Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    invoices: Mapped[List["Invoice"]] = relationship("Invoice", back_populates="contract", lazy="select")


class Invoice(Base):
    __tablename__ = "invoices"

    id:              Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    company_id:      Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    contract_id:     Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("contracts.id", ondelete="SET NULL"))
    invoice_number:  Mapped[str] = mapped_column(String(32), unique=True)
    status:          Mapped[InvoiceStatus] = mapped_column(Enum(InvoiceStatus), default=InvoiceStatus.DRAFT)
    issue_date:      Mapped[Optional[date]] = mapped_column(Date)
    due_date:        Mapped[Optional[date]] = mapped_column(Date)
    subtotal_cents:  Mapped[int] = mapped_column(Integer, default=0)
    tax_cents:       Mapped[int] = mapped_column(Integer, default=0)
    total_cents:     Mapped[int] = mapped_column(Integer, default=0)
    currency:        Mapped[str] = mapped_column(String(3), default="USD")
    notes:           Mapped[Optional[str]] = mapped_column(Text)
    erp_exported:    Mapped[bool] = mapped_column(default=False)
    created_at:      Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    contract: Mapped[Optional["Contract"]] = relationship("Contract", back_populates="invoices", lazy="select")
    line_items: Mapped[List["InvoiceLineItem"]] = relationship("InvoiceLineItem", back_populates="invoice", lazy="select")


class InvoiceLineItem(Base):
    __tablename__ = "invoice_line_items"

    id:          Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    invoice_id:  Mapped[str] = mapped_column(String(36), ForeignKey("invoices.id", ondelete="CASCADE"))
    description: Mapped[str] = mapped_column(String(256))
    quantity:    Mapped[float] = mapped_column(Float, default=1.0)
    unit_price_cents: Mapped[int] = mapped_column(Integer)
    total_cents: Mapped[int] = mapped_column(Integer)
    source_type: Mapped[Optional[str]] = mapped_column(String(32))  # "work_order", "usage", "subscription"
    source_id:   Mapped[Optional[str]] = mapped_column(String(36))

    invoice: Mapped["Invoice"] = relationship("Invoice", back_populates="line_items")


# ── Pydantic schemas ───────────────────────────────────────────────────────────
class ContractCreate(BaseModel):
    company_id:       str
    title:            str
    pricing_model:    PricingModel = PricingModel.FIXED
    start_date:       Optional[date] = None
    end_date:         Optional[date] = None
    value_cents:      Optional[int] = None
    monthly_fee_cents: Optional[int] = None
    sla_uptime_pct:   Optional[float] = None
    sla_response_hours: Optional[int] = None
    notes:            Optional[str] = None


class ContractOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id:              str
    company_id:      str
    contract_number: str
    title:           str
    pricing_model:   PricingModel
    status:          ContractStatus
    start_date:      Optional[date]
    end_date:        Optional[date]
    value_cents:     Optional[int]
    monthly_fee_cents: Optional[int]
    sla_uptime_pct:  Optional[float]
    sla_response_hours: Optional[int]
    created_at:      datetime


class LineItemIn(BaseModel):
    description:      str
    quantity:         float = 1.0
    unit_price_cents: int
    source_type:      Optional[str] = None
    source_id:        Optional[str] = None


class InvoiceCreate(BaseModel):
    company_id:  str
    contract_id: Optional[str] = None
    issue_date:  Optional[date] = None
    due_date:    Optional[date] = None
    currency:    str = "USD"
    notes:       Optional[str] = None
    line_items:  List[LineItemIn] = []


class LineItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id:          int
    description: str
    quantity:    float
    unit_price_cents: int
    total_cents: int
    source_type: Optional[str]
    source_id:   Optional[str]


class InvoiceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id:             str
    company_id:     str
    contract_id:    Optional[str]
    invoice_number: str
    status:         InvoiceStatus
    issue_date:     Optional[date]
    due_date:       Optional[date]
    subtotal_cents: int
    tax_cents:      int
    total_cents:    int
    currency:       str
    erp_exported:   bool
    created_at:     datetime
    line_items:     List[LineItemOut] = []
