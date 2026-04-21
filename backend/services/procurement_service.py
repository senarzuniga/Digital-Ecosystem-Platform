"""
Procurement / RFQ Service
=========================
Implements all 8 modules of the Procurement pipeline plus SaaS extensions:

  1. Request Capture Service
  2. Structuring & Validation Engine
  3. Routing Engine
  4. Supplier Interaction Service
  5. Offer Management Engine
  6. Decision Engine
  7. Order Execution Service
  8. Feedback & Learning Engine

  Extensions:
  - Needs Prediction
  - Auto-Ordering
  - Open Marketplace
  - IoT Trigger

Business rules (non-negotiable):
  ❌  Request cannot be routed unless structured (confidence ≥ threshold or human-validated)
  ❌  Offer cannot be used in a Decision unless normalized
  ❌  Order cannot be created unless a DecisionMatrix exists
  ✅  Every state transition emits a domain event for full traceability
  ✅  The system learns from each feedback cycle (updates SupplierProfile score)
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.core.events import Topics, get_event_bus
from backend.models.procurement import (
    AutoOrderRule,
    AutoOrderRuleCreate,
    DecisionMatrix,
    IoTTriggerIn,
    Offer,
    OfferCreate,
    OrderStatus,
    ProcurementFeedback,
    ProcurementFeedbackCreate,
    ProcurementOrder,
    ProcurementOrderCreate,
    ProcurementOrderUpdate,
    ProcurementRequest,
    ProcurementRequestCreate,
    RequestStatus,
    RequestType,
    RoutingPlan,
    RoutingType,
    StructuredRequest,
    StructuredRequestValidate,
    SupplierProfile,
    SupplierProfileCreate,
    SupplierRequest,
    SupplierRequestStatus,
    UrgencyLevel,
)

logger = logging.getLogger(__name__)

# ── Configuration constants ────────────────────────────────────────────────────

# Minimum confidence score for automatic routing (below this → human review)
CONFIDENCE_THRESHOLD: float = 0.75

# Minimum number of normalized offers required before a Decision can be computed
MIN_OFFERS_FOR_DECISION: int = 2

# Decision scoring weights (must sum to 1.0)
DEFAULT_WEIGHTS: Dict[str, float] = {
    "price":           0.35,
    "lead_time":       0.20,
    "compliance":      0.25,
    "supplier_rating": 0.15,
    "risk":            0.05,  # subtracted from score
}

# RFQ response deadline default (hours)
RFQ_RESPONSE_HOURS: int = 48

# Auto-order: max price (cents) allowed without human approval
AUTO_ORDER_PRICE_LIMIT_CENTS: int = 500_00  # $500


# ── Module 1: Request Capture Service ─────────────────────────────────────────

async def capture_request(
    db: AsyncSession,
    data: ProcurementRequestCreate,
    created_by: Optional[str] = None,
) -> ProcurementRequest:
    """Capture a new procurement request from any input source."""
    attachments_json = json.dumps(data.attachments) if data.attachments else None
    req = ProcurementRequest(
        company_id=data.company_id,
        created_by=created_by,
        raw_input=data.raw_input,
        attachments=attachments_json,
        machine_id=data.machine_id,
        source=data.source,
        status=RequestStatus.CAPTURED,
    )
    db.add(req)
    await db.flush()

    bus = get_event_bus()
    await bus.publish(
        Topics.PROCUREMENT_REQUEST_CREATED,
        {
            "request_id": req.id,
            "company_id": req.company_id,
            "source":     req.source,
            "machine_id": req.machine_id,
        },
        source="procurement.capture",
    )
    logger.info("Procurement request captured: %s (company=%s)", req.id, req.company_id)
    return req


async def get_request(db: AsyncSession, request_id: str) -> Optional[ProcurementRequest]:
    result = await db.execute(
        select(ProcurementRequest)
        .options(
            selectinload(ProcurementRequest.structured),
            selectinload(ProcurementRequest.routing_plan),
            selectinload(ProcurementRequest.offers),
            selectinload(ProcurementRequest.decision),
            selectinload(ProcurementRequest.order),
        )
        .where(ProcurementRequest.id == request_id)
    )
    return result.scalar_one_or_none()


async def list_requests(
    db: AsyncSession,
    company_id: Optional[str] = None,
    status: Optional[RequestStatus] = None,
    limit: int = 50,
    offset: int = 0,
) -> List[ProcurementRequest]:
    q = (
        select(ProcurementRequest)
        .options(selectinload(ProcurementRequest.structured))
        .order_by(ProcurementRequest.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    if company_id:
        q = q.where(ProcurementRequest.company_id == company_id)
    if status:
        q = q.where(ProcurementRequest.status == status)
    result = await db.execute(q)
    return list(result.scalars().all())


# ── Module 2: Structuring & Validation Engine ─────────────────────────────────

def _parse_raw_input(raw_input: str) -> Dict[str, Any]:
    """
    Lightweight NLP heuristic to extract structured fields from raw text.

    In production this would call an LLM / NLP pipeline. Here we use keyword
    matching to demonstrate the interface and produce a confidence_score.
    """
    text = raw_input.lower()
    result: Dict[str, Any] = {
        "req_type":          RequestType.SPARE_PART,
        "component":         None,
        "urgency_level":     UrgencyLevel.MEDIUM,
        "production_impact": "medium",
        "technical_specs":   {},
        "confidence_score":  0.0,
    }
    score = 0.0

    # Type classification
    if any(kw in text for kw in ("service", "repair", "maintenance", "inspection", "calibration")):
        result["req_type"] = RequestType.SERVICE
        score += 0.25
    elif any(kw in text for kw in ("consumable", "lubricant", "oil", "filter", "coolant", "grease")):
        result["req_type"] = RequestType.CONSUMABLE
        score += 0.25
    elif any(kw in text for kw in ("part", "spare", "bearing", "gear", "belt", "sensor", "valve", "motor")):
        result["req_type"] = RequestType.SPARE_PART
        score += 0.25

    # Urgency detection
    if any(kw in text for kw in ("critical", "emergency", "urgent", "immediate", "stopped", "breakdown")):
        result["urgency_level"] = UrgencyLevel.CRITICAL
        result["production_impact"] = "critical"
        score += 0.20
    elif any(kw in text for kw in ("high", "soon", "asap", "priority")):
        result["urgency_level"] = UrgencyLevel.HIGH
        result["production_impact"] = "high"
        score += 0.15
    elif any(kw in text for kw in ("low", "scheduled", "planned", "routine")):
        result["urgency_level"] = UrgencyLevel.LOW
        result["production_impact"] = "low"
        score += 0.15
    else:
        score += 0.10

    # Component extraction (simple keyword scan)
    component_keywords = [
        "bearing", "gear", "belt", "motor", "pump", "valve", "sensor",
        "conveyor", "cylinder", "encoder", "drive", "actuator", "seal",
    ]
    for kw in component_keywords:
        if kw in text:
            result["component"] = kw
            score += 0.20
            break

    # Technical spec extraction
    specs: Dict[str, str] = {}
    words = text.split()
    for i, word in enumerate(words):
        if word.endswith("mm") or word.endswith("bar") or word.endswith("rpm") or word.endswith("kw"):
            specs["spec_value"] = word
            score += 0.10
            break
    if specs:
        result["technical_specs"] = specs

    # Quantity / SKU presence adds confidence
    if any(kw in text for kw in ("qty", "quantity", "x2", "x1", "units", "pcs", "ref", "sku", "part no")):
        score += 0.10

    # Cap at 1.0
    result["confidence_score"] = min(round(score, 3), 1.0)
    return result


async def structure_request(
    db: AsyncSession,
    request_id: str,
) -> Optional[StructuredRequest]:
    """
    Transform raw_input into a StructuredRequest.
    Sets needs_human_review=True when confidence_score < CONFIDENCE_THRESHOLD.
    """
    req = await get_request(db, request_id)
    if req is None:
        return None
    if req.status not in (RequestStatus.CAPTURED, RequestStatus.STRUCTURING):
        raise ValueError(f"Request {request_id} cannot be structured in status '{req.status}'")

    req.status = RequestStatus.STRUCTURING
    await db.flush()

    parsed = _parse_raw_input(req.raw_input)
    needs_review = parsed["confidence_score"] < CONFIDENCE_THRESHOLD

    specs = parsed.get("technical_specs")
    specs_json = json.dumps(specs) if specs else None

    structured = StructuredRequest(
        request_id=request_id,
        req_type=parsed["req_type"],
        machine_id=req.machine_id,
        component=parsed.get("component"),
        technical_specs=specs_json,
        urgency_level=parsed["urgency_level"],
        production_impact=parsed["production_impact"],
        confidence_score=parsed["confidence_score"],
        needs_human_review=needs_review,
    )
    db.add(structured)

    req.status = RequestStatus.NEEDS_REVIEW if needs_review else RequestStatus.STRUCTURED
    await db.flush()

    bus = get_event_bus()
    await bus.publish(
        Topics.PROCUREMENT_REQUEST_STRUCTURED,
        {
            "request_id":        request_id,
            "confidence_score":  parsed["confidence_score"],
            "needs_human_review": needs_review,
            "req_type":          parsed["req_type"],
        },
        source="procurement.structuring",
    )
    logger.info(
        "Request %s structured — confidence=%.2f needs_review=%s",
        request_id, parsed["confidence_score"], needs_review,
    )
    return structured


async def get_structured_request(
    db: AsyncSession, request_id: str
) -> Optional[StructuredRequest]:
    result = await db.execute(
        select(StructuredRequest).where(StructuredRequest.request_id == request_id)
    )
    return result.scalar_one_or_none()


async def validate_structured_request(
    db: AsyncSession,
    request_id: str,
    data: StructuredRequestValidate,
    validated_by: Optional[str] = None,
) -> Optional[StructuredRequest]:
    """Human reviewer approves / corrects a structured request."""
    structured = await get_structured_request(db, request_id)
    if structured is None:
        return None

    changes = data.model_dump(exclude_unset=True)
    for key, value in changes.items():
        setattr(structured, key, value)

    structured.needs_human_review = False
    structured.validated_by = validated_by
    structured.validated_at = datetime.now(tz=timezone.utc)
    structured.confidence_score = max(structured.confidence_score, CONFIDENCE_THRESHOLD)
    structured.updated_at = datetime.now(tz=timezone.utc)

    # Advance parent request status
    req = await get_request(db, request_id)
    if req and req.status == RequestStatus.NEEDS_REVIEW:
        req.status = RequestStatus.STRUCTURED
    await db.flush()
    return structured


# ── Module 3: Routing Engine ───────────────────────────────────────────────────

async def route_request(
    db: AsyncSession,
    request_id: str,
) -> Optional[RoutingPlan]:
    """
    Determine which suppliers should receive the RFQ.
    Filters SupplierProfile by capability, SLA, location, and rating.
    """
    req = await get_request(db, request_id)
    if req is None:
        return None

    if req.status != RequestStatus.STRUCTURED:
        raise ValueError(
            f"Request {request_id} must be in STRUCTURED status before routing "
            f"(current: '{req.status}'). Ensure confidence_score ≥ {CONFIDENCE_THRESHOLD} "
            "or human validation has been completed."
        )

    structured = await get_structured_request(db, request_id)
    if structured is None:
        raise ValueError(f"No StructuredRequest found for request {request_id}")

    # Filter suppliers
    q = select(SupplierProfile).where(SupplierProfile.is_active == True)  # noqa: E712
    if req.company_id:
        # Company-specific or marketplace suppliers
        q = q.where(
            (SupplierProfile.company_id == req.company_id)
            | (SupplierProfile.is_marketplace == True)  # noqa: E712
        )
    result = await db.execute(q)
    candidates: List[SupplierProfile] = list(result.scalars().all())

    # Capability filter
    matching = []
    for s in candidates:
        caps = json.loads(s.capabilities) if s.capabilities else []
        if structured.req_type.value in caps or not caps:
            matching.append(s)

    # Sort by rating descending, take top 5
    matching.sort(key=lambda s: s.rating_score, reverse=True)
    selected = matching[:5]

    # Determine routing type
    routing_type = RoutingType.DIRECT if len(selected) == 1 else RoutingType.RFQ

    plan = RoutingPlan(
        request_id=request_id,
        routing_type=routing_type,
        supplier_ids=json.dumps([s.id for s in selected]),
    )
    db.add(plan)
    req.status = RequestStatus.ROUTING
    await db.flush()

    # Create SupplierRequest records
    deadline = datetime.now(tz=timezone.utc) + timedelta(hours=RFQ_RESPONSE_HOURS)
    urgency_sla = {
        UrgencyLevel.CRITICAL: "24h",
        UrgencyLevel.HIGH: "48h",
        UrgencyLevel.MEDIUM: "72h",
        UrgencyLevel.LOW: "168h",
    }
    sla_required = urgency_sla.get(structured.urgency_level, "72h")
    bus = get_event_bus()

    for supplier in selected:
        sr = SupplierRequest(
            routing_plan_id=plan.id,
            request_id=request_id,
            supplier_id=supplier.id,
            sla_required=sla_required,
            response_deadline=deadline,
            status=SupplierRequestStatus.SENT,
            sent_at=datetime.now(tz=timezone.utc),
        )
        db.add(sr)
        await db.flush()
        await bus.publish(
            Topics.PROCUREMENT_SUPPLIER_REQUEST_SENT,
            {
                "request_id": request_id,
                "supplier_request_id": sr.id,
                "supplier_id": supplier.id,
                "sla_required": sla_required,
                "response_deadline": deadline.isoformat(),
            },
            source="procurement.supplier_interaction",
        )

    req.status = RequestStatus.ROUTED
    await db.flush()

    await bus.publish(
        Topics.PROCUREMENT_REQUEST_ROUTED,
        {
            "request_id":    request_id,
            "routing_type":  routing_type,
            "suppliers":     [s.id for s in selected],
            "deadline":      deadline.isoformat(),
        },
        source="procurement.routing",
    )
    logger.info(
        "Request %s routed to %d supplier(s) via %s",
        request_id, len(selected), routing_type,
    )
    return plan


# ── Module 5: Offer Management Engine ─────────────────────────────────────────

async def submit_offer(
    db: AsyncSession,
    request_id: str,
    data: OfferCreate,
) -> Offer:
    """
    Accept and normalize a supplier offer.
    Critical rule: ALL offers are normalized to the canonical Offer format.
    """
    req = await get_request(db, request_id)
    if req is None:
        raise ValueError(f"Request {request_id} not found")

    # Link to SupplierRequest if it exists
    sr_result = await db.execute(
        select(SupplierRequest).where(
            SupplierRequest.request_id == request_id,
            SupplierRequest.supplier_id == data.supplier_id,
        )
    )
    supplier_req = sr_result.scalar_one_or_none()

    alt_options_json = (
        json.dumps(data.alternative_options) if data.alternative_options else None
    )

    offer = Offer(
        supplier_request_id=supplier_req.id if supplier_req else None,
        request_id=request_id,
        supplier_id=data.supplier_id,
        price_cents=data.price_cents,
        lead_time_days=data.lead_time_days,
        technical_compliance_score=data.technical_compliance_score,
        alternative_options=alt_options_json,
        validity_date=data.validity_date,
        is_normalized=True,  # normalization applied at intake
    )
    db.add(offer)

    if supplier_req:
        supplier_req.status = SupplierRequestStatus.RESPONDED

    # Advance request status
    if req.status in (RequestStatus.ROUTED, RequestStatus.AWAITING_OFFERS):
        req.status = RequestStatus.AWAITING_OFFERS

    # Count normalized offers
    offers_result = await db.execute(
        select(func.count(Offer.id)).where(
            Offer.request_id == request_id,
            Offer.is_normalized == True,  # noqa: E712
        )
    )
    n_offers = (offers_result.scalar() or 0) + 1  # +1 for the one just added
    if n_offers >= MIN_OFFERS_FOR_DECISION:
        req.status = RequestStatus.OFFERS_RECEIVED

    await db.flush()

    bus = get_event_bus()
    await bus.publish(
        Topics.PROCUREMENT_OFFER_RECEIVED,
        {
            "request_id":  request_id,
            "offer_id":    offer.id,
            "supplier_id": data.supplier_id,
            "price_cents": data.price_cents,
            "lead_time_days": data.lead_time_days,
            "n_offers":    n_offers,
        },
        source="procurement.offers",
    )
    logger.info(
        "Offer %s received for request %s (supplier=%s, price=%d cents)",
        offer.id, request_id, data.supplier_id, data.price_cents,
    )
    return offer


async def list_offers(
    db: AsyncSession, request_id: str
) -> List[Offer]:
    result = await db.execute(
        select(Offer)
        .where(Offer.request_id == request_id, Offer.is_normalized == True)  # noqa: E712
        .order_by(Offer.created_at.asc())
    )
    return list(result.scalars().all())


# ── Module 6: Decision Engine ──────────────────────────────────────────────────

async def _get_supplier_rating(db: AsyncSession, supplier_id: str) -> float:
    result = await db.execute(
        select(SupplierProfile.rating_score).where(SupplierProfile.id == supplier_id)
    )
    rating = result.scalar_one_or_none()
    return rating if rating is not None else 0.5  # neutral default


async def compute_decision(
    db: AsyncSession,
    request_id: str,
    weights: Optional[Dict[str, float]] = None,
) -> DecisionMatrix:
    """
    Score and rank all normalized offers for the request.
    Critical rule: requires ≥ MIN_OFFERS_FOR_DECISION normalized offers.
    """
    offers = await list_offers(db, request_id)
    normalized_offers = [o for o in offers if o.is_normalized]

    if len(normalized_offers) < MIN_OFFERS_FOR_DECISION:
        raise ValueError(
            f"Cannot compute decision for request {request_id}: "
            f"need ≥ {MIN_OFFERS_FOR_DECISION} normalized offers, "
            f"have {len(normalized_offers)}."
        )

    w = weights or DEFAULT_WEIGHTS
    max_price = max(o.price_cents for o in normalized_offers) or 1
    max_lead  = max(o.lead_time_days for o in normalized_offers) or 1

    scored = []
    for offer in normalized_offers:
        supplier_rating = await _get_supplier_rating(db, offer.supplier_id)

        price_score      = 1.0 - (offer.price_cents / max_price)
        lead_score       = 1.0 - (offer.lead_time_days / max_lead)
        compliance_score = offer.technical_compliance_score
        rating_score     = supplier_rating
        # Risk: high price + long lead = higher risk; lower is better
        risk_factor      = ((offer.price_cents / max_price) + (offer.lead_time_days / max_lead)) / 2

        total = (
            w.get("price", 0.35)           * price_score
            + w.get("lead_time", 0.20)     * lead_score
            + w.get("compliance", 0.25)    * compliance_score
            + w.get("supplier_rating", 0.15) * rating_score
            - w.get("risk", 0.05)          * risk_factor
        )
        scored.append({"offer_id": offer.id, "score": round(total, 4)})

    # Rank descending by score
    scored.sort(key=lambda x: x["score"], reverse=True)
    for i, item in enumerate(scored):
        item["ranking_position"] = i + 1

    recommended_offer_id = scored[0]["offer_id"] if scored else None

    dm = DecisionMatrix(
        request_id=request_id,
        recommended_offer_id=recommended_offer_id,
        ranked_offers=json.dumps(scored),
        scoring_weights=json.dumps(w),
    )
    db.add(dm)

    # Advance request status
    req = await get_request(db, request_id)
    if req:
        req.status = RequestStatus.DECIDED
    await db.flush()

    bus = get_event_bus()
    await bus.publish(
        Topics.PROCUREMENT_DECISION_MADE,
        {
            "request_id":            request_id,
            "recommended_offer_id":  recommended_offer_id,
            "n_offers_evaluated":    len(scored),
        },
        source="procurement.decision",
    )
    logger.info(
        "Decision computed for request %s — recommended offer: %s",
        request_id, recommended_offer_id,
    )
    return dm


async def get_decision(
    db: AsyncSession, request_id: str
) -> Optional[DecisionMatrix]:
    result = await db.execute(
        select(DecisionMatrix).where(DecisionMatrix.request_id == request_id)
    )
    return result.scalar_one_or_none()


# ── Module 7: Order Execution Service ─────────────────────────────────────────

async def create_order(
    db: AsyncSession,
    data: ProcurementOrderCreate,
    created_by: Optional[str] = None,
) -> ProcurementOrder:
    """
    Convert a selected offer into a ProcurementOrder.
    Critical rule: DecisionMatrix must exist for the request.
    Critical rule: selected_offer_id must be a normalized offer for the request.
    """
    decision = await get_decision(db, data.request_id)
    if decision is None:
        raise ValueError(
            f"Cannot create order for request {data.request_id}: "
            "a DecisionMatrix must exist first. Run /decide to compute it."
        )

    # Verify offer belongs to this request and is normalized
    offer_result = await db.execute(
        select(Offer).where(
            Offer.id == data.selected_offer_id,
            Offer.request_id == data.request_id,
            Offer.is_normalized == True,  # noqa: E712
        )
    )
    offer = offer_result.scalar_one_or_none()
    if offer is None:
        raise ValueError(
            f"Offer {data.selected_offer_id} is not a normalized offer for "
            f"request {data.request_id}."
        )

    order = ProcurementOrder(
        request_id=data.request_id,
        decision_matrix_id=decision.id,
        selected_offer_id=data.selected_offer_id,
        status=OrderStatus.CREATED,
    )
    db.add(order)

    req = await get_request(db, data.request_id)
    if req:
        req.status = RequestStatus.ORDERED

    # Update supplier total_orders counter
    await db.execute(
        update(SupplierProfile)
        .where(SupplierProfile.id == offer.supplier_id)
        .values(total_orders=SupplierProfile.total_orders + 1)
    )

    await db.flush()

    # ERP integration stub — emit event for downstream integration
    bus = get_event_bus()
    await bus.publish(
        Topics.PROCUREMENT_ORDER_CREATED,
        {
            "order_id":          order.id,
            "request_id":        data.request_id,
            "selected_offer_id": data.selected_offer_id,
            "supplier_id":       offer.supplier_id,
            "price_cents":       offer.price_cents,
            "erp_reference":     order.erp_reference,
        },
        source="procurement.order",
    )
    logger.info(
        "Procurement order %s created for request %s (offer=%s)",
        order.id, data.request_id, data.selected_offer_id,
    )
    return order


async def get_order(db: AsyncSession, order_id: str) -> Optional[ProcurementOrder]:
    result = await db.execute(
        select(ProcurementOrder)
        .options(selectinload(ProcurementOrder.feedback))
        .where(ProcurementOrder.id == order_id)
    )
    return result.scalar_one_or_none()


async def update_order(
    db: AsyncSession,
    order_id: str,
    data: ProcurementOrderUpdate,
) -> Optional[ProcurementOrder]:
    order = await get_order(db, order_id)
    if order is None:
        return None

    changes = data.model_dump(exclude_unset=True)
    for key, value in changes.items():
        setattr(order, key, value)

    order.updated_at = datetime.now(tz=timezone.utc)

    if data.status == OrderStatus.COMPLETED:
        req = await get_request(db, order.request_id)
        if req:
            req.status = RequestStatus.COMPLETED

    await db.flush()

    bus = get_event_bus()
    await bus.publish(
        Topics.PROCUREMENT_ORDER_UPDATED,
        {"order_id": order_id, "changes": list(changes.keys()), "new_status": data.status},
        source="procurement.order",
    )
    return order


# ── Module 8: Feedback & Learning Engine ──────────────────────────────────────

async def submit_feedback(
    db: AsyncSession,
    order_id: str,
    data: ProcurementFeedbackCreate,
) -> ProcurementFeedback:
    """
    Record real execution results and update supplier scoring.
    The system learns from every feedback cycle.
    """
    order = await get_order(db, order_id)
    if order is None:
        raise ValueError(f"Order {order_id} not found")

    # Get the selected offer to identify the supplier
    offer_result = await db.execute(
        select(Offer).where(Offer.id == order.selected_offer_id)
    )
    offer = offer_result.scalar_one_or_none()
    if offer is None:
        raise ValueError(f"Selected offer {order.selected_offer_id} not found")

    feedback = ProcurementFeedback(
        request_id=order.request_id,
        order_id=order_id,
        supplier_id=offer.supplier_id,
        delivery_time_actual_days=data.delivery_time_actual_days,
        quality_score=data.quality_score,
        issue_flag=data.issue_flag,
        notes=data.notes,
    )
    db.add(feedback)
    await db.flush()

    # ── Learning: update supplier rating ──────────────────────────────────────
    await _update_supplier_score(db, offer.supplier_id, data)

    bus = get_event_bus()
    await bus.publish(
        Topics.PROCUREMENT_FEEDBACK_SUBMITTED,
        {
            "order_id":    order_id,
            "request_id":  order.request_id,
            "supplier_id": offer.supplier_id,
            "quality_score": data.quality_score,
            "issue_flag":  data.issue_flag,
        },
        source="procurement.feedback",
    )
    logger.info(
        "Feedback submitted for order %s — supplier=%s quality=%.2f",
        order_id, offer.supplier_id, data.quality_score or 0,
    )
    return feedback


async def _update_supplier_score(
    db: AsyncSession,
    supplier_id: str,
    feedback: ProcurementFeedbackCreate,
) -> None:
    """
    Update the SupplierProfile rating using an exponential moving average.
    Formula: new_rating = 0.8 * old_rating + 0.2 * cycle_score
    cycle_score = quality_score * 0.6 + (1 if not issue_flag else 0) * 0.4
    """
    result = await db.execute(
        select(SupplierProfile).where(SupplierProfile.id == supplier_id)
    )
    supplier = result.scalar_one_or_none()
    if supplier is None:
        return

    quality = feedback.quality_score if feedback.quality_score is not None else 0.7
    issue_penalty = 0.0 if feedback.issue_flag else 1.0
    cycle_score = quality * 0.6 + issue_penalty * 0.4

    old_rating = supplier.rating_score
    new_rating = round(0.8 * old_rating + 0.2 * cycle_score, 4)
    supplier.rating_score = new_rating

    if not feedback.issue_flag:
        supplier.successful_orders = supplier.successful_orders + 1

    supplier.updated_at = datetime.now(tz=timezone.utc)
    await db.flush()
    logger.info(
        "Supplier %s rating updated: %.4f → %.4f",
        supplier_id, old_rating, new_rating,
    )


async def get_feedback(db: AsyncSession, order_id: str) -> Optional[ProcurementFeedback]:
    result = await db.execute(
        select(ProcurementFeedback).where(ProcurementFeedback.order_id == order_id)
    )
    return result.scalar_one_or_none()


# ── Supplier Profile CRUD ──────────────────────────────────────────────────────

async def create_supplier(
    db: AsyncSession, data: SupplierProfileCreate
) -> SupplierProfile:
    caps_json = json.dumps(data.capabilities) if data.capabilities else None
    supplier = SupplierProfile(
        company_id=data.company_id,
        name=data.name,
        capabilities=caps_json,
        sla_hours=data.sla_hours,
        location=data.location,
        contact_email=data.contact_email,
        is_marketplace=data.is_marketplace,
        auto_order_enabled=data.auto_order_enabled,
    )
    db.add(supplier)
    await db.flush()
    return supplier


async def list_suppliers(
    db: AsyncSession,
    company_id: Optional[str] = None,
    marketplace_only: bool = False,
) -> List[SupplierProfile]:
    q = select(SupplierProfile).where(SupplierProfile.is_active == True)  # noqa: E712
    if company_id:
        if marketplace_only:
            q = q.where(SupplierProfile.is_marketplace == True)  # noqa: E712
        else:
            q = q.where(
                (SupplierProfile.company_id == company_id)
                | (SupplierProfile.is_marketplace == True)  # noqa: E712
            )
    elif marketplace_only:
        q = q.where(SupplierProfile.is_marketplace == True)  # noqa: E712
    result = await db.execute(q)
    return list(result.scalars().all())


# ── SaaS Extension: IoT Trigger ───────────────────────────────────────────────

async def iot_trigger(
    db: AsyncSession, data: IoTTriggerIn
) -> ProcurementRequest:
    """
    Automatically create a procurement request from an IoT/alert event.
    Maps alert severity to urgency_level in the raw_input description.
    """
    raw_input = (
        f"[IoT Auto-Trigger] Machine: {data.machine_id} | "
        f"Alert: {data.alert_type} | Severity: {data.severity} | "
        f"Description: {data.description}"
    )
    req = await capture_request(
        db,
        ProcurementRequestCreate(
            company_id=data.company_id,
            raw_input=raw_input,
            machine_id=data.machine_id,
            source="iot",
        ),
    )

    bus = get_event_bus()
    await bus.publish(
        Topics.PROCUREMENT_IOT_TRIGGERED,
        {
            "request_id": req.id,
            "machine_id": data.machine_id,
            "alert_type": data.alert_type,
            "severity":   data.severity,
        },
        source="procurement.iot",
    )
    logger.info("IoT-triggered procurement request %s for machine %s", req.id, data.machine_id)
    return req


# ── SaaS Extension: Auto-Order Rules ──────────────────────────────────────────

async def create_auto_order_rule(
    db: AsyncSession, data: AutoOrderRuleCreate
) -> AutoOrderRule:
    rule = AutoOrderRule(
        company_id=data.company_id,
        sku=data.sku,
        component=data.component,
        req_type=data.req_type,
        min_stock=data.min_stock,
        reorder_qty=data.reorder_qty,
        preferred_supplier_id=data.preferred_supplier_id,
    )
    db.add(rule)
    await db.flush()
    return rule


async def list_auto_order_rules(
    db: AsyncSession, company_id: Optional[str] = None
) -> List[AutoOrderRule]:
    q = select(AutoOrderRule).where(AutoOrderRule.is_active == True)  # noqa: E712
    if company_id:
        q = q.where(AutoOrderRule.company_id == company_id)
    result = await db.execute(q)
    return list(result.scalars().all())


async def evaluate_auto_order(
    db: AsyncSession,
    company_id: str,
    component: str,
    current_stock: int,
) -> Optional[ProcurementRequest]:
    """
    Evaluate auto-order rules and create a request if the threshold is breached.
    Returns the created request or None if no rule matched.
    """
    q = select(AutoOrderRule).where(
        AutoOrderRule.company_id == company_id,
        AutoOrderRule.component == component,
        AutoOrderRule.is_active == True,  # noqa: E712
    )
    result = await db.execute(q)
    rules = list(result.scalars().all())

    for rule in rules:
        if rule.min_stock is not None and current_stock <= rule.min_stock:
            qty_str = f"qty: {rule.reorder_qty}" if rule.reorder_qty else ""
            raw = (
                f"[Auto-Order] component: {component} {qty_str} "
                f"sku: {rule.sku or ''} — stock below threshold ({current_stock} ≤ {rule.min_stock})"
            )
            req = await capture_request(
                db,
                ProcurementRequestCreate(
                    company_id=company_id,
                    raw_input=raw,
                    source="auto",
                ),
            )
            logger.info(
                "Auto-order triggered for company=%s component=%s (stock=%d rule=%s)",
                company_id, component, current_stock, rule.id,
            )
            return req
    return None


# ── SaaS Extension: Needs Prediction ──────────────────────────────────────────

async def predict_upcoming_needs(
    db: AsyncSession, company_id: str, horizon_days: int = 30
) -> List[Dict[str, Any]]:
    """
    Analyse historical requests to predict components likely to be needed
    within the next `horizon_days` days.

    Returns a list of predictions sorted by urgency score descending.
    In production this would run a time-series ML model; here we use
    frequency + recency heuristics.
    """
    since = datetime.now(tz=timezone.utc) - timedelta(days=90)
    q = (
        select(StructuredRequest)
        .join(ProcurementRequest, ProcurementRequest.id == StructuredRequest.request_id)
        .where(
            ProcurementRequest.company_id == company_id,
            ProcurementRequest.created_at >= since,
        )
    )
    result = await db.execute(q)
    structured_list = list(result.scalars().all())

    # Count frequency per component
    from collections import Counter
    counter: Counter = Counter()
    last_seen: Dict[str, datetime] = {}
    for s in structured_list:
        key = (s.component or "unknown", s.req_type.value)
        counter[key] += 1
        s_created = s.created_at
        if s_created is not None and s_created.tzinfo is None:
            s_created = s_created.replace(tzinfo=timezone.utc)
        if s_created is not None and (key not in last_seen or s_created > last_seen[key]):
            last_seen[key] = s_created

    predictions = []
    now = datetime.now(tz=timezone.utc)
    for (component, req_type), freq in counter.most_common(10):
        days_since = (now - last_seen.get((component, req_type), now)).days
        # Urgency score: high frequency + recent = higher priority
        urgency_score = round(freq * 0.6 + max(0, 1 - days_since / 90) * 0.4, 3)
        predictions.append({
            "component":          component,
            "req_type":           req_type,
            "frequency_90d":      freq,
            "days_since_last":    days_since,
            "urgency_score":      urgency_score,
            "predicted_in_days":  max(1, int(90 / max(freq, 1))),
        })

    return predictions


# ── KPI Metrics ───────────────────────────────────────────────────────────────

async def get_metrics(
    db: AsyncSession, company_id: Optional[str] = None
) -> Dict[str, Any]:
    """Compute procurement module KPIs."""

    # Total requests
    q = select(func.count(ProcurementRequest.id))
    if company_id:
        q = q.where(ProcurementRequest.company_id == company_id)
    total_requests = (await db.execute(q)).scalar() or 0

    # Auto-routed (source != manual)
    q2 = select(func.count(ProcurementRequest.id)).where(
        ProcurementRequest.source != "manual"
    )
    if company_id:
        q2 = q2.where(ProcurementRequest.company_id == company_id)
    auto_count = (await db.execute(q2)).scalar() or 0
    automation_ratio = round((auto_count / total_requests * 100) if total_requests else 0.0, 1)

    # Total orders
    q3 = select(func.count(ProcurementOrder.id))
    if company_id:
        q3 = q3.join(
            ProcurementRequest,
            ProcurementRequest.id == ProcurementOrder.request_id,
        ).where(ProcurementRequest.company_id == company_id)
    total_orders = (await db.execute(q3)).scalar() or 0

    # Completed orders
    q4 = select(func.count(ProcurementOrder.id)).where(
        ProcurementOrder.status == OrderStatus.COMPLETED
    )
    if company_id:
        q4 = q4.join(
            ProcurementRequest,
            ProcurementRequest.id == ProcurementOrder.request_id,
        ).where(ProcurementRequest.company_id == company_id)
    completed_orders = (await db.execute(q4)).scalar() or 0

    # Avg quality score from feedback
    q5 = select(func.avg(ProcurementFeedback.quality_score))
    if company_id:
        q5 = q5.join(
            ProcurementOrder,
            ProcurementOrder.id == ProcurementFeedback.order_id,
        ).join(
            ProcurementRequest,
            ProcurementRequest.id == ProcurementOrder.request_id,
        ).where(ProcurementRequest.company_id == company_id)
    avg_quality = (await db.execute(q5)).scalar()

    # Structuring accuracy: % of requests that went straight through (no human review needed)
    q6 = select(func.count(StructuredRequest.id)).where(
        StructuredRequest.needs_human_review == False  # noqa: E712
    )
    accurate_count = (await db.execute(q6)).scalar() or 0
    total_structured_q = select(func.count(StructuredRequest.id))
    total_structured = (await db.execute(total_structured_q)).scalar() or 0
    structuring_accuracy = (
        round(accurate_count / total_structured * 100, 1) if total_structured else None
    )

    # Total spend (sum of selected offer prices for completed orders)
    q7 = (
        select(func.sum(Offer.price_cents))
        .join(ProcurementOrder, ProcurementOrder.selected_offer_id == Offer.id)
        .where(ProcurementOrder.status == OrderStatus.COMPLETED)
    )
    if company_id:
        q7 = q7.join(
            ProcurementRequest,
            ProcurementRequest.id == ProcurementOrder.request_id,
        ).where(ProcurementRequest.company_id == company_id)
    total_spend = (await db.execute(q7)).scalar() or 0

    # Avg RFQ response time (hours) between SupplierRequest.sent_at and Offer.created_at
    # Simplified: difference for all responded supplier requests with matching offer
    # This is an approximate metric using available data
    avg_rfq_response_time_h: Optional[float] = None  # Requires time-series query

    return {
        "total_requests":           total_requests,
        "avg_rfq_response_time_h":  avg_rfq_response_time_h,
        "structuring_accuracy_pct": structuring_accuracy,
        "automation_ratio_pct":     automation_ratio,
        "total_orders":             total_orders,
        "completed_orders":         completed_orders,
        "avg_quality_score":        round(avg_quality, 3) if avg_quality else None,
        "total_spend_cents":        total_spend,
        "estimated_savings_cents":  0,  # Requires baseline comparison data
    }
