"""
SQLAlchemy ORM models + Pydantic schemas for the Procurement / RFQ module.

Data flow:
  ProcurementRequest
    → StructuredRequest
    → RoutingPlan
      → SupplierRequest  (one per supplier)
        → Offer           (one per supplier response)
    → DecisionMatrix
    → ProcurementOrder
      → ProcurementFeedback

Supporting entity: SupplierProfile
"""

from __future__ import annotations

import enum
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.core.database import Base


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


# ── Enums ──────────────────────────────────────────────────────────────────────

class RequestStatus(str, enum.Enum):
    CAPTURED          = "captured"
    STRUCTURING       = "structuring"
    NEEDS_REVIEW      = "needs_review"
    STRUCTURED        = "structured"
    ROUTING           = "routing"
    ROUTED            = "routed"
    AWAITING_OFFERS   = "awaiting_offers"
    OFFERS_RECEIVED   = "offers_received"
    DECIDED           = "decided"
    ORDERED           = "ordered"
    COMPLETED         = "completed"
    CANCELLED         = "cancelled"


class RequestType(str, enum.Enum):
    SERVICE    = "SERVICE"
    SPARE_PART = "SPARE_PART"
    CONSUMABLE = "CONSUMABLE"


class UrgencyLevel(str, enum.Enum):
    CRITICAL  = "critical"
    HIGH      = "high"
    MEDIUM    = "medium"
    LOW       = "low"


class RoutingType(str, enum.Enum):
    DIRECT = "DIRECT"
    RFQ    = "RFQ"


class SupplierRequestStatus(str, enum.Enum):
    PENDING   = "pending"
    SENT      = "sent"
    RESPONDED = "responded"
    EXPIRED   = "expired"


class OrderStatus(str, enum.Enum):
    CREATED     = "CREATED"
    SENT        = "SENT"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED   = "COMPLETED"
    CANCELLED   = "CANCELLED"


# ── ORM Models ────────────────────────────────────────────────────────────────

class ProcurementRequest(Base):
    """Module 1 — Request Capture Service output."""

    __tablename__ = "procurement_requests"

    id:          Mapped[str]           = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    company_id:  Mapped[str]           = mapped_column(String(64), index=True, nullable=False)
    created_by:  Mapped[Optional[str]] = mapped_column(String(36))
    raw_input:   Mapped[str]           = mapped_column(Text, nullable=False)
    attachments: Mapped[Optional[str]] = mapped_column(Text)          # JSON list of file refs
    machine_id:  Mapped[Optional[str]] = mapped_column(String(36))
    source:      Mapped[str]           = mapped_column(String(32), default="manual")  # manual|iot|auto
    status:      Mapped[RequestStatus] = mapped_column(
        Enum(RequestStatus), default=RequestStatus.CAPTURED, index=True
    )
    created_at:  Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at:  Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    structured:    Mapped[Optional["StructuredRequest"]] = relationship(
        "StructuredRequest", back_populates="request", uselist=False, lazy="select"
    )
    routing_plan:  Mapped[Optional["RoutingPlan"]] = relationship(
        "RoutingPlan", back_populates="request", uselist=False, lazy="select"
    )
    offers:        Mapped[List["Offer"]] = relationship(
        "Offer", back_populates="request", lazy="select"
    )
    decision:      Mapped[Optional["DecisionMatrix"]] = relationship(
        "DecisionMatrix", back_populates="request", uselist=False, lazy="select"
    )
    order:         Mapped[Optional["ProcurementOrder"]] = relationship(
        "ProcurementOrder", back_populates="request", uselist=False, lazy="select"
    )


class StructuredRequest(Base):
    """Module 2 — Structuring & Validation Engine output."""

    __tablename__ = "structured_requests"

    id:                  Mapped[str]           = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    request_id:          Mapped[str]           = mapped_column(String(36), ForeignKey("procurement_requests.id", ondelete="CASCADE"), unique=True, index=True)
    req_type:            Mapped[RequestType]   = mapped_column(Enum(RequestType))
    machine_id:          Mapped[Optional[str]] = mapped_column(String(36))
    component:           Mapped[Optional[str]] = mapped_column(String(256))
    technical_specs:     Mapped[Optional[str]] = mapped_column(Text)        # JSON
    urgency_level:       Mapped[UrgencyLevel]  = mapped_column(Enum(UrgencyLevel), default=UrgencyLevel.MEDIUM)
    production_impact:   Mapped[Optional[str]] = mapped_column(String(64))  # low|medium|high|critical
    confidence_score:    Mapped[float]         = mapped_column(Float, default=0.0)
    needs_human_review:  Mapped[bool]          = mapped_column(Boolean, default=False)
    validated_by:        Mapped[Optional[str]] = mapped_column(String(36))
    validated_at:        Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at:          Mapped[datetime]      = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at:          Mapped[datetime]      = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    request: Mapped["ProcurementRequest"] = relationship("ProcurementRequest", back_populates="structured")


class RoutingPlan(Base):
    """Module 3 — Routing Engine output."""

    __tablename__ = "routing_plans"

    id:           Mapped[str]         = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    request_id:   Mapped[str]         = mapped_column(String(36), ForeignKey("procurement_requests.id", ondelete="CASCADE"), unique=True, index=True)
    routing_type: Mapped[RoutingType] = mapped_column(Enum(RoutingType), default=RoutingType.RFQ)
    supplier_ids: Mapped[str]         = mapped_column(Text)  # JSON list of supplier UUIDs
    created_at:   Mapped[datetime]    = mapped_column(DateTime(timezone=True), default=_utcnow)

    request:           Mapped["ProcurementRequest"] = relationship("ProcurementRequest", back_populates="routing_plan")
    supplier_requests: Mapped[List["SupplierRequest"]] = relationship("SupplierRequest", back_populates="routing_plan", lazy="select")


class SupplierRequest(Base):
    """Module 4 — Supplier Interaction Service: outbound request to a single supplier."""

    __tablename__ = "supplier_requests"

    id:                Mapped[str]                  = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    routing_plan_id:   Mapped[str]                  = mapped_column(String(36), ForeignKey("routing_plans.id", ondelete="CASCADE"), index=True)
    request_id:        Mapped[str]                  = mapped_column(String(36), ForeignKey("procurement_requests.id", ondelete="CASCADE"), index=True)
    supplier_id:       Mapped[str]                  = mapped_column(String(36), index=True)
    sla_required:      Mapped[Optional[str]]        = mapped_column(String(64))
    response_deadline: Mapped[Optional[datetime]]   = mapped_column(DateTime(timezone=True))
    sent_at:           Mapped[Optional[datetime]]   = mapped_column(DateTime(timezone=True))
    status:            Mapped[SupplierRequestStatus] = mapped_column(
        Enum(SupplierRequestStatus), default=SupplierRequestStatus.PENDING
    )

    routing_plan: Mapped["RoutingPlan"]  = relationship("RoutingPlan", back_populates="supplier_requests")
    offer:        Mapped[Optional["Offer"]] = relationship("Offer", back_populates="supplier_request", uselist=False, lazy="select")


class Offer(Base):
    """Module 5 — Offer Management Engine: normalized offer from a supplier."""

    __tablename__ = "procurement_offers"

    id:                         Mapped[str]           = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    supplier_request_id:        Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("supplier_requests.id", ondelete="SET NULL"), index=True)
    request_id:                 Mapped[str]           = mapped_column(String(36), ForeignKey("procurement_requests.id", ondelete="CASCADE"), index=True)
    supplier_id:                Mapped[str]           = mapped_column(String(36), index=True)
    price_cents:                Mapped[int]           = mapped_column(Integer)          # always in smallest currency unit
    lead_time_days:             Mapped[int]           = mapped_column(Integer)
    technical_compliance_score: Mapped[float]         = mapped_column(Float, default=0.0)  # 0-1
    alternative_options:        Mapped[Optional[str]] = mapped_column(Text)   # JSON
    validity_date:              Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    is_normalized:              Mapped[bool]          = mapped_column(Boolean, default=False)
    created_at:                 Mapped[datetime]      = mapped_column(DateTime(timezone=True), default=_utcnow)

    request:          Mapped["ProcurementRequest"] = relationship("ProcurementRequest", back_populates="offers")
    supplier_request: Mapped[Optional["SupplierRequest"]] = relationship("SupplierRequest", back_populates="offer")


class DecisionMatrix(Base):
    """Module 6 — Decision Engine output."""

    __tablename__ = "decision_matrices"

    id:                   Mapped[str]           = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    request_id:           Mapped[str]           = mapped_column(String(36), ForeignKey("procurement_requests.id", ondelete="CASCADE"), unique=True, index=True)
    recommended_offer_id: Mapped[Optional[str]] = mapped_column(String(36))
    ranked_offers:        Mapped[str]           = mapped_column(Text)  # JSON list of {offer_id, score, ranking_position}
    scoring_weights:      Mapped[Optional[str]] = mapped_column(Text)  # JSON weights used
    created_at:           Mapped[datetime]      = mapped_column(DateTime(timezone=True), default=_utcnow)

    request: Mapped["ProcurementRequest"] = relationship("ProcurementRequest", back_populates="decision")
    order:   Mapped[Optional["ProcurementOrder"]] = relationship("ProcurementOrder", back_populates="decision", uselist=False, lazy="select")


class ProcurementOrder(Base):
    """Module 7 — Order Execution Service."""

    __tablename__ = "procurement_orders"

    id:                  Mapped[str]         = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    request_id:          Mapped[str]         = mapped_column(String(36), ForeignKey("procurement_requests.id", ondelete="CASCADE"), unique=True, index=True)
    decision_matrix_id:  Mapped[str]         = mapped_column(String(36), ForeignKey("decision_matrices.id", ondelete="RESTRICT"))
    selected_offer_id:   Mapped[str]         = mapped_column(String(36), ForeignKey("procurement_offers.id", ondelete="RESTRICT"))
    status:              Mapped[OrderStatus] = mapped_column(Enum(OrderStatus), default=OrderStatus.CREATED, index=True)
    tracking_info:       Mapped[Optional[str]] = mapped_column(Text)  # JSON
    erp_reference:       Mapped[Optional[str]] = mapped_column(String(128))
    created_at:          Mapped[datetime]    = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at:          Mapped[datetime]    = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    request:  Mapped["ProcurementRequest"] = relationship("ProcurementRequest", back_populates="order")
    decision: Mapped["DecisionMatrix"]     = relationship("DecisionMatrix", back_populates="order")
    feedback: Mapped[Optional["ProcurementFeedback"]] = relationship("ProcurementFeedback", back_populates="order", uselist=False, lazy="select")


class ProcurementFeedback(Base):
    """Module 8 — Feedback & Learning Engine input."""

    __tablename__ = "procurement_feedback"

    id:                      Mapped[str]           = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    request_id:              Mapped[str]           = mapped_column(String(36), ForeignKey("procurement_requests.id", ondelete="CASCADE"), index=True)
    order_id:                Mapped[str]           = mapped_column(String(36), ForeignKey("procurement_orders.id", ondelete="CASCADE"), unique=True, index=True)
    supplier_id:             Mapped[str]           = mapped_column(String(36), index=True)
    delivery_time_actual_days: Mapped[Optional[int]] = mapped_column(Integer)
    quality_score:           Mapped[Optional[float]] = mapped_column(Float)   # 0-1
    issue_flag:              Mapped[bool]          = mapped_column(Boolean, default=False)
    notes:                   Mapped[Optional[str]] = mapped_column(Text)
    created_at:              Mapped[datetime]      = mapped_column(DateTime(timezone=True), default=_utcnow)

    order: Mapped["ProcurementOrder"] = relationship("ProcurementOrder", back_populates="feedback")


class SupplierProfile(Base):
    """Supporting entity for routing and learning engine."""

    __tablename__ = "supplier_profiles"

    id:               Mapped[str]           = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    company_id:       Mapped[Optional[str]] = mapped_column(String(64), index=True)  # None = global marketplace
    name:             Mapped[str]           = mapped_column(String(256), nullable=False)
    capabilities:     Mapped[Optional[str]] = mapped_column(Text)    # JSON list: ["SERVICE","SPARE_PART",...]
    sla_hours:        Mapped[Optional[int]] = mapped_column(Integer)
    location:         Mapped[Optional[str]] = mapped_column(String(256))
    rating_score:     Mapped[float]         = mapped_column(Float, default=1.0)  # 0-1, starts neutral
    total_orders:     Mapped[int]           = mapped_column(Integer, default=0)
    successful_orders: Mapped[int]          = mapped_column(Integer, default=0)
    is_active:        Mapped[bool]          = mapped_column(Boolean, default=True)
    is_marketplace:   Mapped[bool]          = mapped_column(Boolean, default=False)
    contact_email:    Mapped[Optional[str]] = mapped_column(String(256))
    auto_order_enabled: Mapped[bool]        = mapped_column(Boolean, default=False)
    created_at:       Mapped[datetime]      = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at:       Mapped[datetime]      = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)


class AutoOrderRule(Base):
    """SaaS extension: rules for automatic re-ordering."""

    __tablename__ = "auto_order_rules"

    id:             Mapped[str]           = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    company_id:     Mapped[str]           = mapped_column(String(64), index=True, nullable=False)
    sku:            Mapped[Optional[str]] = mapped_column(String(128))
    component:      Mapped[Optional[str]] = mapped_column(String(256))
    req_type:       Mapped[RequestType]   = mapped_column(Enum(RequestType))
    min_stock:      Mapped[Optional[int]] = mapped_column(Integer)   # trigger threshold
    reorder_qty:    Mapped[Optional[int]] = mapped_column(Integer)
    preferred_supplier_id: Mapped[Optional[str]] = mapped_column(String(36))
    is_active:      Mapped[bool]          = mapped_column(Boolean, default=True)
    created_at:     Mapped[datetime]      = mapped_column(DateTime(timezone=True), default=_utcnow)


# ── Pydantic Input/Output Schemas ─────────────────────────────────────────────

class ProcurementRequestCreate(BaseModel):
    company_id: str
    raw_input:  str
    machine_id: Optional[str] = None
    attachments: Optional[List[str]] = None
    source: str = "manual"


class ProcurementRequestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id:          str
    company_id:  str
    created_by:  Optional[str]
    raw_input:   str
    attachments: Optional[str]
    machine_id:  Optional[str]
    source:      str
    status:      RequestStatus
    created_at:  datetime
    updated_at:  datetime


class StructuredRequestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id:                  str
    request_id:          str
    req_type:            RequestType
    machine_id:          Optional[str]
    component:           Optional[str]
    technical_specs:     Optional[str]
    urgency_level:       UrgencyLevel
    production_impact:   Optional[str]
    confidence_score:    float
    needs_human_review:  bool
    validated_by:        Optional[str]
    validated_at:        Optional[datetime]
    created_at:          datetime
    updated_at:          datetime


class StructuredRequestValidate(BaseModel):
    """Payload for human reviewer to confirm / correct a structured request."""
    req_type:          Optional[RequestType] = None
    machine_id:        Optional[str] = None
    component:         Optional[str] = None
    technical_specs:   Optional[str] = None
    urgency_level:     Optional[UrgencyLevel] = None
    production_impact: Optional[str] = None


class RoutingPlanOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id:           str
    request_id:   str
    routing_type: RoutingType
    supplier_ids: str
    created_at:   datetime


class OfferCreate(BaseModel):
    """Used by suppliers (or internal simulation) to submit an offer."""
    supplier_id:                str
    price_cents:                int = Field(..., gt=0)
    lead_time_days:             int = Field(..., gt=0)
    technical_compliance_score: float = Field(..., ge=0.0, le=1.0)
    alternative_options:        Optional[List[Dict[str, Any]]] = None
    validity_date:              Optional[datetime] = None


class OfferOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id:                         str
    request_id:                 str
    supplier_id:                str
    price_cents:                int
    lead_time_days:             int
    technical_compliance_score: float
    alternative_options:        Optional[str]
    validity_date:              Optional[datetime]
    is_normalized:              bool
    created_at:                 datetime


class RankedOffer(BaseModel):
    offer_id:         str
    score:            float
    ranking_position: int


class DecisionMatrixOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id:                   str
    request_id:           str
    recommended_offer_id: Optional[str]
    ranked_offers:        str
    scoring_weights:      Optional[str]
    created_at:           datetime


class ProcurementOrderCreate(BaseModel):
    request_id:        str
    selected_offer_id: str


class ProcurementOrderUpdate(BaseModel):
    status:        Optional[OrderStatus] = None
    tracking_info: Optional[str] = None
    erp_reference: Optional[str] = None


class ProcurementOrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id:                 str
    request_id:         str
    decision_matrix_id: str
    selected_offer_id:  str
    status:             OrderStatus
    tracking_info:      Optional[str]
    erp_reference:      Optional[str]
    created_at:         datetime
    updated_at:         datetime


class ProcurementFeedbackCreate(BaseModel):
    delivery_time_actual_days: Optional[int] = None
    quality_score:             Optional[float] = Field(None, ge=0.0, le=1.0)
    issue_flag:                bool = False
    notes:                     Optional[str] = None


class ProcurementFeedbackOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id:                        str
    request_id:                str
    order_id:                  str
    supplier_id:               str
    delivery_time_actual_days: Optional[int]
    quality_score:             Optional[float]
    issue_flag:                bool
    notes:                     Optional[str]
    created_at:                datetime


class SupplierProfileCreate(BaseModel):
    company_id:     Optional[str] = None
    name:           str
    capabilities:   Optional[List[str]] = None
    sla_hours:      Optional[int] = None
    location:       Optional[str] = None
    contact_email:  Optional[str] = None
    is_marketplace: bool = False
    auto_order_enabled: bool = False


class SupplierProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id:               str
    company_id:       Optional[str]
    name:             str
    capabilities:     Optional[str]
    sla_hours:        Optional[int]
    location:         Optional[str]
    rating_score:     float
    total_orders:     int
    successful_orders: int
    is_active:        bool
    is_marketplace:   bool
    contact_email:    Optional[str]
    auto_order_enabled: bool
    created_at:       datetime
    updated_at:       datetime


class AutoOrderRuleCreate(BaseModel):
    company_id:            str
    sku:                   Optional[str] = None
    component:             Optional[str] = None
    req_type:              RequestType
    min_stock:             Optional[int] = None
    reorder_qty:           Optional[int] = None
    preferred_supplier_id: Optional[str] = None


class AutoOrderRuleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id:             str
    company_id:     str
    sku:            Optional[str]
    component:      Optional[str]
    req_type:       RequestType
    min_stock:      Optional[int]
    reorder_qty:    Optional[int]
    preferred_supplier_id: Optional[str]
    is_active:      bool
    created_at:     datetime


class IoTTriggerIn(BaseModel):
    """Payload from IoT/alert system to auto-create a procurement request."""
    company_id:  str
    machine_id:  str
    asset_id:    Optional[str] = None
    alert_type:  str
    description: str
    severity:    str = "medium"


class ProcurementMetrics(BaseModel):
    """KPIs for the procurement module."""
    total_requests:            int
    avg_rfq_response_time_h:   Optional[float]
    structuring_accuracy_pct:  Optional[float]
    automation_ratio_pct:      float
    total_orders:              int
    completed_orders:          int
    avg_quality_score:         Optional[float]
    total_spend_cents:         int
    estimated_savings_cents:   int
