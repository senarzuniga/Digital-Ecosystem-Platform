"""
Procurement / RFQ router.

Endpoints:
  POST   /procurement/requests                          Capture a new request
  GET    /procurement/requests                          List requests
  GET    /procurement/requests/{id}                     Get request detail
  POST   /procurement/requests/{id}/structure           Trigger structuring engine
  GET    /procurement/requests/{id}/structured          Get structured request
  PATCH  /procurement/requests/{id}/structured          Human review / validate
  POST   /procurement/requests/{id}/route               Trigger routing engine
  POST   /procurement/requests/{id}/offers              Submit an offer
  GET    /procurement/requests/{id}/offers              List normalized offers
  POST   /procurement/requests/{id}/decide              Trigger decision engine
  GET    /procurement/requests/{id}/decision            Get decision matrix

  POST   /procurement/orders                            Create order from decision
  GET    /procurement/orders/{id}                       Get order
  PATCH  /procurement/orders/{id}                       Update order status
  POST   /procurement/orders/{id}/feedback              Submit post-execution feedback
  GET    /procurement/orders/{id}/feedback              Get feedback

  POST   /procurement/suppliers                         Register supplier
  GET    /procurement/suppliers                         List suppliers
  GET    /procurement/marketplace/suppliers             Open marketplace suppliers

  POST   /procurement/iot-trigger                       IoT-driven auto-capture
  POST   /procurement/auto-order/evaluate               Evaluate auto-order rules
  GET    /procurement/auto-order/rules                  List auto-order rules
  POST   /procurement/auto-order/rules                  Create auto-order rule
  GET    /procurement/predict                           Predict upcoming needs

  GET    /procurement/metrics                           Module KPIs
"""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from backend.core.security import Role, get_current_user_payload, require_roles
from backend.models.procurement import (
    AutoOrderRuleCreate,
    AutoOrderRuleOut,
    IoTTriggerIn,
    OfferCreate,
    OfferOut,
    DecisionMatrixOut,
    ProcurementFeedbackCreate,
    ProcurementFeedbackOut,
    ProcurementMetrics,
    ProcurementOrderCreate,
    ProcurementOrderOut,
    ProcurementOrderUpdate,
    ProcurementRequestCreate,
    ProcurementRequestOut,
    RequestStatus,
    StructuredRequestOut,
    StructuredRequestValidate,
    SupplierProfileCreate,
    SupplierProfileOut,
)
from backend.services import procurement_service

router = APIRouter(prefix="/procurement", tags=["Procurement / RFQ"])


# ── Request Capture ────────────────────────────────────────────────────────────

@router.post(
    "/requests",
    response_model=ProcurementRequestOut,
    status_code=status.HTTP_201_CREATED,
    summary="Capture a new procurement request",
)
async def capture_request(
    data: ProcurementRequestCreate,
    payload: dict = Depends(get_current_user_payload),
    db: AsyncSession = Depends(get_db),
):
    req = await procurement_service.capture_request(
        db, data, created_by=payload.get("sub")
    )
    return ProcurementRequestOut.model_validate(req)


@router.get(
    "/requests",
    response_model=List[ProcurementRequestOut],
    summary="List procurement requests",
)
async def list_requests(
    company_id: Optional[str] = Query(None),
    status:     Optional[RequestStatus] = Query(None),
    limit:      int = Query(50, ge=1, le=500),
    offset:     int = Query(0, ge=0),
    _auth: dict = Depends(get_current_user_payload),
    db: AsyncSession = Depends(get_db),
):
    reqs = await procurement_service.list_requests(
        db, company_id=company_id, status=status, limit=limit, offset=offset
    )
    return [ProcurementRequestOut.model_validate(r) for r in reqs]


@router.get(
    "/requests/{request_id}",
    response_model=ProcurementRequestOut,
    summary="Get a procurement request",
)
async def get_request(
    request_id: str,
    _auth: dict = Depends(get_current_user_payload),
    db: AsyncSession = Depends(get_db),
):
    req = await procurement_service.get_request(db, request_id)
    if req is None:
        raise HTTPException(status_code=404, detail="Request not found")
    return ProcurementRequestOut.model_validate(req)


# ── Structuring Engine ─────────────────────────────────────────────────────────

@router.post(
    "/requests/{request_id}/structure",
    response_model=StructuredRequestOut,
    status_code=status.HTTP_201_CREATED,
    summary="Trigger structuring & validation engine",
)
async def structure_request(
    request_id: str,
    _auth: dict = Depends(get_current_user_payload),
    db: AsyncSession = Depends(get_db),
):
    try:
        structured = await procurement_service.structure_request(db, request_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if structured is None:
        raise HTTPException(status_code=404, detail="Request not found")
    return StructuredRequestOut.model_validate(structured)


@router.get(
    "/requests/{request_id}/structured",
    response_model=StructuredRequestOut,
    summary="Get the structured view of a request",
)
async def get_structured_request(
    request_id: str,
    _auth: dict = Depends(get_current_user_payload),
    db: AsyncSession = Depends(get_db),
):
    structured = await procurement_service.get_structured_request(db, request_id)
    if structured is None:
        raise HTTPException(status_code=404, detail="Structured request not found. Run /structure first.")
    return StructuredRequestOut.model_validate(structured)


@router.patch(
    "/requests/{request_id}/structured",
    response_model=StructuredRequestOut,
    summary="Human review: validate / correct structured request",
)
async def validate_structured_request(
    request_id: str,
    data: StructuredRequestValidate,
    payload: dict = Depends(get_current_user_payload),
    db: AsyncSession = Depends(get_db),
):
    structured = await procurement_service.validate_structured_request(
        db, request_id, data, validated_by=payload.get("sub")
    )
    if structured is None:
        raise HTTPException(status_code=404, detail="Structured request not found")
    return StructuredRequestOut.model_validate(structured)


# ── Routing Engine ─────────────────────────────────────────────────────────────

@router.post(
    "/requests/{request_id}/route",
    response_model=dict,
    status_code=status.HTTP_201_CREATED,
    summary="Trigger routing engine — selects suppliers and sends RFQs",
)
async def route_request(
    request_id: str,
    _auth: dict = Depends(get_current_user_payload),
    db: AsyncSession = Depends(get_db),
):
    try:
        plan = await procurement_service.route_request(db, request_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if plan is None:
        raise HTTPException(status_code=404, detail="Request not found")
    import json
    return {
        "routing_plan_id": plan.id,
        "request_id":      plan.request_id,
        "routing_type":    plan.routing_type,
        "supplier_ids":    json.loads(plan.supplier_ids),
        "created_at":      plan.created_at.isoformat(),
    }


# ── Offer Management Engine ────────────────────────────────────────────────────

@router.post(
    "/requests/{request_id}/offers",
    response_model=OfferOut,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a normalized supplier offer",
)
async def submit_offer(
    request_id: str,
    data: OfferCreate,
    _auth: dict = Depends(get_current_user_payload),
    db: AsyncSession = Depends(get_db),
):
    try:
        offer = await procurement_service.submit_offer(db, request_id, data)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return OfferOut.model_validate(offer)


@router.get(
    "/requests/{request_id}/offers",
    response_model=List[OfferOut],
    summary="List normalized offers for a request",
)
async def list_offers(
    request_id: str,
    _auth: dict = Depends(get_current_user_payload),
    db: AsyncSession = Depends(get_db),
):
    offers = await procurement_service.list_offers(db, request_id)
    return [OfferOut.model_validate(o) for o in offers]


# ── Decision Engine ────────────────────────────────────────────────────────────

@router.post(
    "/requests/{request_id}/decide",
    response_model=DecisionMatrixOut,
    status_code=status.HTTP_201_CREATED,
    summary="Compute decision matrix and recommendation",
)
async def compute_decision(
    request_id: str,
    _auth: dict = Depends(get_current_user_payload),
    db: AsyncSession = Depends(get_db),
):
    try:
        matrix = await procurement_service.compute_decision(db, request_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return DecisionMatrixOut.model_validate(matrix)


@router.get(
    "/requests/{request_id}/decision",
    response_model=DecisionMatrixOut,
    summary="Get decision matrix for a request",
)
async def get_decision(
    request_id: str,
    _auth: dict = Depends(get_current_user_payload),
    db: AsyncSession = Depends(get_db),
):
    matrix = await procurement_service.get_decision(db, request_id)
    if matrix is None:
        raise HTTPException(status_code=404, detail="Decision not found. Run /decide first.")
    return DecisionMatrixOut.model_validate(matrix)


# ── Order Execution ────────────────────────────────────────────────────────────

@router.post(
    "/orders",
    response_model=ProcurementOrderOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create a procurement order from a decision",
)
async def create_order(
    data: ProcurementOrderCreate,
    payload: dict = Depends(get_current_user_payload),
    db: AsyncSession = Depends(get_db),
):
    try:
        order = await procurement_service.create_order(db, data, created_by=payload.get("sub"))
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return ProcurementOrderOut.model_validate(order)


@router.get(
    "/orders/{order_id}",
    response_model=ProcurementOrderOut,
    summary="Get procurement order",
)
async def get_order(
    order_id: str,
    _auth: dict = Depends(get_current_user_payload),
    db: AsyncSession = Depends(get_db),
):
    order = await procurement_service.get_order(db, order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return ProcurementOrderOut.model_validate(order)


@router.patch(
    "/orders/{order_id}",
    response_model=ProcurementOrderOut,
    summary="Update order status / tracking / ERP reference",
)
async def update_order(
    order_id: str,
    data: ProcurementOrderUpdate,
    _auth: dict = Depends(get_current_user_payload),
    db: AsyncSession = Depends(get_db),
):
    order = await procurement_service.update_order(db, order_id, data)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return ProcurementOrderOut.model_validate(order)


# ── Feedback & Learning ────────────────────────────────────────────────────────

@router.post(
    "/orders/{order_id}/feedback",
    response_model=ProcurementFeedbackOut,
    status_code=status.HTTP_201_CREATED,
    summary="Submit post-execution feedback (triggers learning engine)",
)
async def submit_feedback(
    order_id: str,
    data: ProcurementFeedbackCreate,
    _auth: dict = Depends(get_current_user_payload),
    db: AsyncSession = Depends(get_db),
):
    try:
        feedback = await procurement_service.submit_feedback(db, order_id, data)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return ProcurementFeedbackOut.model_validate(feedback)


@router.get(
    "/orders/{order_id}/feedback",
    response_model=ProcurementFeedbackOut,
    summary="Get feedback for an order",
)
async def get_feedback(
    order_id: str,
    _auth: dict = Depends(get_current_user_payload),
    db: AsyncSession = Depends(get_db),
):
    feedback = await procurement_service.get_feedback(db, order_id)
    if feedback is None:
        raise HTTPException(status_code=404, detail="Feedback not found")
    return ProcurementFeedbackOut.model_validate(feedback)


# ── Supplier Management ────────────────────────────────────────────────────────

@router.post(
    "/suppliers",
    response_model=SupplierProfileOut,
    status_code=status.HTTP_201_CREATED,
    summary="Register a supplier profile",
)
async def create_supplier(
    data: SupplierProfileCreate,
    _auth: dict = Depends(require_roles(Role.ADMIN, Role.MANAGER)),
    db: AsyncSession = Depends(get_db),
):
    supplier = await procurement_service.create_supplier(db, data)
    return SupplierProfileOut.model_validate(supplier)


@router.get(
    "/suppliers",
    response_model=List[SupplierProfileOut],
    summary="List suppliers (company-specific + marketplace)",
)
async def list_suppliers(
    company_id: Optional[str] = Query(None),
    _auth: dict = Depends(get_current_user_payload),
    db: AsyncSession = Depends(get_db),
):
    suppliers = await procurement_service.list_suppliers(db, company_id=company_id)
    return [SupplierProfileOut.model_validate(s) for s in suppliers]


@router.get(
    "/marketplace/suppliers",
    response_model=List[SupplierProfileOut],
    summary="Open marketplace — all publicly available suppliers",
)
async def marketplace_suppliers(
    _auth: dict = Depends(get_current_user_payload),
    db: AsyncSession = Depends(get_db),
):
    suppliers = await procurement_service.list_suppliers(db, marketplace_only=True)
    return [SupplierProfileOut.model_validate(s) for s in suppliers]


# ── SaaS Extensions ────────────────────────────────────────────────────────────

@router.post(
    "/iot-trigger",
    response_model=ProcurementRequestOut,
    status_code=status.HTTP_201_CREATED,
    summary="[IoT] Auto-create a procurement request from a machine alert",
)
async def iot_trigger(
    data: IoTTriggerIn,
    _auth: dict = Depends(get_current_user_payload),
    db: AsyncSession = Depends(get_db),
):
    req = await procurement_service.iot_trigger(db, data)
    return ProcurementRequestOut.model_validate(req)


@router.post(
    "/auto-order/rules",
    response_model=AutoOrderRuleOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create an auto-ordering rule",
)
async def create_auto_order_rule(
    data: AutoOrderRuleCreate,
    _auth: dict = Depends(require_roles(Role.ADMIN, Role.MANAGER)),
    db: AsyncSession = Depends(get_db),
):
    rule = await procurement_service.create_auto_order_rule(db, data)
    return AutoOrderRuleOut.model_validate(rule)


@router.get(
    "/auto-order/rules",
    response_model=List[AutoOrderRuleOut],
    summary="List auto-ordering rules",
)
async def list_auto_order_rules(
    company_id: Optional[str] = Query(None),
    _auth: dict = Depends(get_current_user_payload),
    db: AsyncSession = Depends(get_db),
):
    rules = await procurement_service.list_auto_order_rules(db, company_id=company_id)
    return [AutoOrderRuleOut.model_validate(r) for r in rules]


@router.post(
    "/auto-order/evaluate",
    response_model=Optional[ProcurementRequestOut],
    summary="Evaluate auto-order rules for a component/stock level",
)
async def evaluate_auto_order(
    company_id: str = Query(...),
    component: str = Query(...),
    current_stock: int = Query(..., ge=0),
    _auth: dict = Depends(get_current_user_payload),
    db: AsyncSession = Depends(get_db),
):
    req = await procurement_service.evaluate_auto_order(db, company_id, component, current_stock)
    if req is None:
        return None
    return ProcurementRequestOut.model_validate(req)


@router.get(
    "/predict",
    summary="Predict upcoming procurement needs (SaaS AI extension)",
)
async def predict_needs(
    company_id: str = Query(...),
    horizon_days: int = Query(30, ge=1, le=365),
    _auth: dict = Depends(get_current_user_payload),
    db: AsyncSession = Depends(get_db),
):
    predictions = await procurement_service.predict_upcoming_needs(db, company_id, horizon_days)
    return {"company_id": company_id, "horizon_days": horizon_days, "predictions": predictions}


# ── KPI Metrics ────────────────────────────────────────────────────────────────

@router.get(
    "/metrics",
    response_model=ProcurementMetrics,
    summary="Procurement module KPIs",
)
async def get_metrics(
    company_id: Optional[str] = Query(None),
    _auth: dict = Depends(get_current_user_payload),
    db: AsyncSession = Depends(get_db),
):
    metrics = await procurement_service.get_metrics(db, company_id=company_id)
    return ProcurementMetrics(**metrics)
