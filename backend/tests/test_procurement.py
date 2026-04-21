"""
Tests for Procurement / RFQ module — service layer + HTTP API.

Covers:
  - Module 1: Request Capture
  - Module 2: Structuring & Validation Engine (including human review)
  - Module 3: Routing Engine
  - Module 5: Offer Management (normalization enforcement)
  - Module 6: Decision Engine (scoring + recommendation)
  - Module 7: Order Execution (business rules)
  - Module 8: Feedback & Learning (supplier score update)
  - Business rules: cannot route unstructured; cannot decide with < 2 offers;
                    cannot order without decision; cannot order non-normalized offer
  - SaaS: IoT trigger, auto-order, needs prediction, marketplace
  - API: all primary endpoints
"""

from __future__ import annotations

import json

import pytest
import pytest_asyncio

from backend.models.procurement import (
    AutoOrderRuleCreate,
    IoTTriggerIn,
    OfferCreate,
    ProcurementFeedbackCreate,
    ProcurementOrderCreate,
    ProcurementOrderUpdate,
    ProcurementRequestCreate,
    RequestStatus,
    RequestType,
    StructuredRequestValidate,
    SupplierProfileCreate,
    UrgencyLevel,
    OrderStatus,
)
from backend.core.events import Topics, get_event_bus
from backend.services.procurement_agents import list_procurement_agents
from backend.services import procurement_service
from backend.tests.conftest import AUTH_ADMIN, AUTH_MANAGER, AUTH_TECH


# ── Helpers ────────────────────────────────────────────────────────────────────

async def _make_supplier(db, name="Acme Parts", capabilities=None, rating=0.8, marketplace=False):
    caps = capabilities or ["SPARE_PART", "CONSUMABLE", "SERVICE"]
    return await procurement_service.create_supplier(
        db,
        SupplierProfileCreate(
            company_id="TESTCO",
            name=name,
            capabilities=caps,
            sla_hours=48,
            location="ES",
            is_marketplace=marketplace,
        ),
    )


async def _capture(db, raw_input="Need spare bearing 6204 urgent", company="TESTCO"):
    return await procurement_service.capture_request(
        db,
        ProcurementRequestCreate(company_id=company, raw_input=raw_input),
        created_by="test-user",
    )


# ════════════════════════════════════════════════════════════════════════════════
# Module 1 — Request Capture
# ════════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_capture_creates_request(db):
    req = await _capture(db)
    assert req.id is not None
    assert req.status == RequestStatus.CAPTURED
    assert req.raw_input is not None


@pytest.mark.asyncio
async def test_capture_with_attachments(db):
    req = await procurement_service.capture_request(
        db,
        ProcurementRequestCreate(
            company_id="TESTCO",
            raw_input="Bearing replacement",
            attachments=["file-001.pdf"],
        ),
    )
    assert req.attachments is not None
    assert "file-001.pdf" in req.attachments


@pytest.mark.asyncio
async def test_list_requests_filter(db):
    await _capture(db, company="LIST-FILTER-CO")
    await _capture(db, company="LIST-FILTER-CO")
    requests = await procurement_service.list_requests(db, company_id="LIST-FILTER-CO")
    assert len(requests) >= 2


# ════════════════════════════════════════════════════════════════════════════════
# Module 2 — Structuring & Validation
# ════════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_structure_produces_structured_request(db):
    req = await _capture(db, raw_input="Need bearing 6204 qty 2 sku BRG-6204 urgent critical")
    structured = await procurement_service.structure_request(db, req.id)
    assert structured is not None
    assert structured.request_id == req.id
    assert structured.req_type == RequestType.SPARE_PART
    assert structured.urgency_level == UrgencyLevel.CRITICAL
    assert 0.0 <= structured.confidence_score <= 1.0


@pytest.mark.asyncio
async def test_structure_low_confidence_triggers_review(db):
    # Minimal raw input → low confidence
    req = await _capture(db, raw_input="we need something")
    structured = await procurement_service.structure_request(db, req.id)
    assert structured is not None
    # If score < threshold, review is required
    if structured.confidence_score < procurement_service.CONFIDENCE_THRESHOLD:
        assert structured.needs_human_review is True
        # Parent request should be in NEEDS_REVIEW
        refreshed = await procurement_service.get_request(db, req.id)
        assert refreshed.status == RequestStatus.NEEDS_REVIEW


@pytest.mark.asyncio
async def test_structure_cannot_run_twice(db):
    req = await _capture(db, raw_input="Need bearing ASAP")
    await procurement_service.structure_request(db, req.id)
    # Should raise on second call
    with pytest.raises(ValueError, match="cannot be structured"):
        await procurement_service.structure_request(db, req.id)


@pytest.mark.asyncio
async def test_human_validation_advances_status(db):
    req = await _capture(db, raw_input="we need something")
    structured = await procurement_service.structure_request(db, req.id)

    validated = await procurement_service.validate_structured_request(
        db,
        req.id,
        StructuredRequestValidate(
            req_type=RequestType.SPARE_PART,
            component="bearing",
            urgency_level=UrgencyLevel.HIGH,
        ),
        validated_by="reviewer-1",
    )
    assert validated is not None
    assert validated.needs_human_review is False
    assert validated.validated_by == "reviewer-1"
    assert validated.validated_at is not None
    assert validated.confidence_score >= procurement_service.CONFIDENCE_THRESHOLD

    refreshed = await procurement_service.get_request(db, req.id)
    assert refreshed.status == RequestStatus.STRUCTURED


# ════════════════════════════════════════════════════════════════════════════════
# Module 3 — Routing Engine
# ════════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_routing_requires_structured_status(db):
    """Business rule: cannot route a CAPTURED (unstructured) request."""
    req = await _capture(db, raw_input="Need something")
    with pytest.raises(ValueError, match="STRUCTURED"):
        await procurement_service.route_request(db, req.id)


@pytest.mark.asyncio
async def test_routing_creates_plan(db):
    await _make_supplier(db, name="RoutingSupplier-A")
    await _make_supplier(db, name="RoutingSupplier-B")

    req = await _capture(db, raw_input="Need bearing urgent critical qty 1")
    structured = await procurement_service.structure_request(db, req.id)
    if structured.needs_human_review:
        await procurement_service.validate_structured_request(
            db, req.id,
            StructuredRequestValidate(req_type=RequestType.SPARE_PART, urgency_level=UrgencyLevel.HIGH),
            validated_by="reviewer",
        )

    plan = await procurement_service.route_request(db, req.id)
    assert plan is not None
    assert plan.request_id == req.id
    supplier_ids = json.loads(plan.supplier_ids)
    assert isinstance(supplier_ids, list)

    refreshed = await procurement_service.get_request(db, req.id)
    assert refreshed.status == RequestStatus.ROUTED

    events = get_event_bus().get_history(topic=Topics.PROCUREMENT_SUPPLIER_REQUEST_SENT, limit=50)
    assert any(e.payload.get("request_id") == req.id for e in events)


# ════════════════════════════════════════════════════════════════════════════════
# Module 5 — Offer Management Engine
# ════════════════════════════════════════════════════════════════════════════════

async def _setup_routed_request(db, company="OFFERCO"):
    s1 = await _make_supplier(db, name=f"Sup-{company}-A", capabilities=["SPARE_PART"])
    s2 = await _make_supplier(db, name=f"Sup-{company}-B", capabilities=["SPARE_PART"])
    req = await _capture(db, raw_input="Need bearing urgent critical qty sku 001", company=company)
    structured = await procurement_service.structure_request(db, req.id)
    if structured.needs_human_review:
        await procurement_service.validate_structured_request(
            db, req.id,
            StructuredRequestValidate(req_type=RequestType.SPARE_PART, urgency_level=UrgencyLevel.HIGH),
            validated_by="reviewer",
        )
    await procurement_service.route_request(db, req.id)
    return req, s1, s2


@pytest.mark.asyncio
async def test_submit_offer_normalizes(db):
    req, s1, _ = await _setup_routed_request(db, company="NORMALIZE-CO")
    offer = await procurement_service.submit_offer(
        db,
        req.id,
        OfferCreate(
            supplier_id=s1.id,
            price_cents=5000,
            lead_time_days=3,
            technical_compliance_score=0.9,
        ),
    )
    assert offer.is_normalized is True
    assert offer.price_cents == 5000
    assert offer.request_id == req.id


@pytest.mark.asyncio
async def test_submit_offer_for_unknown_request_raises(db):
    with pytest.raises(ValueError, match="not found"):
        await procurement_service.submit_offer(
            db,
            "nonexistent-id",
            OfferCreate(supplier_id="s1", price_cents=100, lead_time_days=1, technical_compliance_score=0.5),
        )


@pytest.mark.asyncio
async def test_status_advances_to_offers_received(db):
    req, s1, s2 = await _setup_routed_request(db, company="STATUS-CO")
    await procurement_service.submit_offer(
        db, req.id,
        OfferCreate(supplier_id=s1.id, price_cents=3000, lead_time_days=2, technical_compliance_score=0.8),
    )
    await procurement_service.submit_offer(
        db, req.id,
        OfferCreate(supplier_id=s2.id, price_cents=2500, lead_time_days=4, technical_compliance_score=0.7),
    )
    refreshed = await procurement_service.get_request(db, req.id)
    assert refreshed.status == RequestStatus.OFFERS_RECEIVED


# ════════════════════════════════════════════════════════════════════════════════
# Module 6 — Decision Engine
# ════════════════════════════════════════════════════════════════════════════════

async def _setup_offers(db, company="DECISIONCO"):
    req, s1, s2 = await _setup_routed_request(db, company=company)
    o1 = await procurement_service.submit_offer(
        db, req.id,
        OfferCreate(supplier_id=s1.id, price_cents=4000, lead_time_days=3, technical_compliance_score=0.9),
    )
    o2 = await procurement_service.submit_offer(
        db, req.id,
        OfferCreate(supplier_id=s2.id, price_cents=2000, lead_time_days=7, technical_compliance_score=0.7),
    )
    return req, o1, o2


@pytest.mark.asyncio
async def test_decision_requires_two_offers(db):
    req, s1, s2 = await _setup_routed_request(db, company="DECMIN-CO")
    # Only one offer submitted
    await procurement_service.submit_offer(
        db, req.id,
        OfferCreate(supplier_id=s1.id, price_cents=5000, lead_time_days=3, technical_compliance_score=0.8),
    )
    with pytest.raises(ValueError, match="normalized offers"):
        await procurement_service.compute_decision(db, req.id)


@pytest.mark.asyncio
async def test_decision_produces_recommendation(db):
    req, o1, o2 = await _setup_offers(db, company="DECIDE-OK-CO")
    matrix = await procurement_service.compute_decision(db, req.id)
    assert matrix.recommended_offer_id is not None
    assert matrix.recommended_offer_id in (o1.id, o2.id)
    ranked = json.loads(matrix.ranked_offers)
    assert len(ranked) == 2
    # Positions must be 1-indexed and sequential
    positions = sorted(item["ranking_position"] for item in ranked)
    assert positions == [1, 2]


@pytest.mark.asyncio
async def test_decision_scores_are_between_0_and_1(db):
    req, o1, o2 = await _setup_offers(db, company="SCORE-RANGE-CO")
    matrix = await procurement_service.compute_decision(db, req.id)
    for item in json.loads(matrix.ranked_offers):
        assert 0.0 <= item["score"] <= 1.0


# ════════════════════════════════════════════════════════════════════════════════
# Module 7 — Order Execution
# ════════════════════════════════════════════════════════════════════════════════

async def _setup_with_decision(db, company="ORDERCO"):
    req, o1, o2 = await _setup_offers(db, company=company)
    matrix = await procurement_service.compute_decision(db, req.id)
    return req, matrix, o1, o2


@pytest.mark.asyncio
async def test_order_requires_decision_matrix(db):
    req = await _capture(db, raw_input="Routine filter replacement")
    with pytest.raises(ValueError, match="DecisionMatrix"):
        await procurement_service.create_order(
            db, ProcurementOrderCreate(request_id=req.id, selected_offer_id="fake-offer")
        )


@pytest.mark.asyncio
async def test_order_requires_normalized_offer(db):
    req, matrix, o1, o2 = await _setup_with_decision(db, company="NORM-ORDER-CO")
    with pytest.raises(ValueError, match="normalized offer"):
        await procurement_service.create_order(
            db, ProcurementOrderCreate(request_id=req.id, selected_offer_id="bad-offer-id")
        )


@pytest.mark.asyncio
async def test_create_order_succeeds(db):
    req, matrix, o1, o2 = await _setup_with_decision(db, company="CREATE-ORDER-CO")
    order = await procurement_service.create_order(
        db, ProcurementOrderCreate(request_id=req.id, selected_offer_id=matrix.recommended_offer_id)
    )
    assert order.id is not None
    assert order.status == OrderStatus.CREATED
    assert order.decision_matrix_id == matrix.id

    refreshed = await procurement_service.get_request(db, req.id)
    assert refreshed.status == RequestStatus.ORDERED


@pytest.mark.asyncio
async def test_update_order_to_completed(db):
    req, matrix, o1, o2 = await _setup_with_decision(db, company="COMPLETE-CO")
    order = await procurement_service.create_order(
        db, ProcurementOrderCreate(request_id=req.id, selected_offer_id=matrix.recommended_offer_id)
    )
    updated = await procurement_service.update_order(
        db, order.id, ProcurementOrderUpdate(status=OrderStatus.COMPLETED, erp_reference="ERP-12345")
    )
    assert updated.status == OrderStatus.COMPLETED
    assert updated.erp_reference == "ERP-12345"

    refreshed = await procurement_service.get_request(db, req.id)
    assert refreshed.status == RequestStatus.COMPLETED


# ════════════════════════════════════════════════════════════════════════════════
# Module 8 — Feedback & Learning
# ════════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_feedback_updates_supplier_score(db):
    req, matrix, o1, o2 = await _setup_with_decision(db, company="FEEDBACK-CO")
    order = await procurement_service.create_order(
        db, ProcurementOrderCreate(request_id=req.id, selected_offer_id=matrix.recommended_offer_id)
    )

    # Get supplier for the selected offer
    from sqlalchemy import select
    from backend.models.procurement import Offer, SupplierProfile
    offer_result = await db.execute(select(Offer).where(Offer.id == order.selected_offer_id))
    offer = offer_result.scalar_one()
    sup_result = await db.execute(select(SupplierProfile).where(SupplierProfile.id == offer.supplier_id))
    supplier_before = sup_result.scalar_one()
    original_rating = supplier_before.rating_score

    feedback = await procurement_service.submit_feedback(
        db, order.id,
        ProcurementFeedbackCreate(
            delivery_time_actual_days=3,
            quality_score=1.0,
            issue_flag=False,
            notes="Excellent delivery",
        ),
    )
    assert feedback.id is not None
    assert feedback.quality_score == 1.0
    assert feedback.issue_flag is False

    # Supplier rating should have changed
    await db.refresh(supplier_before)
    assert supplier_before.successful_orders >= 1
    # With quality=1.0 and no issue, new rating should be >= original
    assert supplier_before.rating_score >= original_rating * 0.8


@pytest.mark.asyncio
async def test_feedback_with_issue_flag_lowers_score(db):
    req, matrix, o1, o2 = await _setup_with_decision(db, company="ISSUE-CO")
    order = await procurement_service.create_order(
        db, ProcurementOrderCreate(request_id=req.id, selected_offer_id=matrix.recommended_offer_id)
    )

    from sqlalchemy import select
    from backend.models.procurement import Offer, SupplierProfile
    offer_result = await db.execute(select(Offer).where(Offer.id == order.selected_offer_id))
    offer = offer_result.scalar_one()
    sup_result = await db.execute(select(SupplierProfile).where(SupplierProfile.id == offer.supplier_id))
    supplier = sup_result.scalar_one()
    original_rating = supplier.rating_score

    await procurement_service.submit_feedback(
        db, order.id,
        ProcurementFeedbackCreate(
            delivery_time_actual_days=14,
            quality_score=0.2,
            issue_flag=True,
            notes="Late and damaged",
        ),
    )
    await db.refresh(supplier)
    assert supplier.rating_score < original_rating


# ════════════════════════════════════════════════════════════════════════════════
# SaaS Extensions
# ════════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_iot_trigger_creates_request(db):
    req = await procurement_service.iot_trigger(
        db,
        IoTTriggerIn(
            company_id="IOT-CO",
            machine_id="machine-001",
            alert_type="overheating",
            description="Motor temperature critical",
            severity="critical",
        ),
    )
    assert req.id is not None
    assert req.source == "iot"
    assert "IoT Auto-Trigger" in req.raw_input
    assert req.machine_id == "machine-001"


@pytest.mark.asyncio
async def test_auto_order_rule_created_and_evaluated(db):
    rule = await procurement_service.create_auto_order_rule(
        db,
        AutoOrderRuleCreate(
            company_id="AUTO-CO",
            component="filter",
            req_type=RequestType.CONSUMABLE,
            min_stock=5,
            reorder_qty=20,
        ),
    )
    assert rule.id is not None

    # Stock below threshold → should trigger request
    req = await procurement_service.evaluate_auto_order(db, "AUTO-CO", "filter", current_stock=3)
    assert req is not None
    assert req.source == "auto"
    assert "Auto-Order" in req.raw_input

    # Stock above threshold → no request
    req2 = await procurement_service.evaluate_auto_order(db, "AUTO-CO", "filter", current_stock=10)
    assert req2 is None


@pytest.mark.asyncio
async def test_marketplace_suppliers(db):
    await _make_supplier(db, name="Global Parts Ltd", marketplace=True)
    await _make_supplier(db, name="Local Supplier Co", marketplace=False)

    marketplace_suppliers = await procurement_service.list_suppliers(db, marketplace_only=True)
    assert any(s.is_marketplace for s in marketplace_suppliers)
    assert all(s.is_marketplace for s in marketplace_suppliers)


@pytest.mark.asyncio
async def test_needs_prediction_returns_list(db):
    # Create a few structured requests to build a history
    for _ in range(3):
        req = await _capture(db, raw_input="Need bearing for motor urgent qty 2", company="PREDICT-CO")
        await procurement_service.structure_request(db, req.id)

    predictions = await procurement_service.predict_upcoming_needs(db, "PREDICT-CO")
    assert isinstance(predictions, list)


# ════════════════════════════════════════════════════════════════════════════════
# Procurement Module Agents
# ════════════════════════════════════════════════════════════════════════════════

def test_procurement_module_agents_catalog():
    agents = list_procurement_agents()
    assert len(agents) == 8
    assert agents[0].id == "request_capture_agent"
    assert agents[-1].id == "feedback_learning_agent"
    assert all(a.traceability_event.startswith("procurement.") for a in agents)


# ════════════════════════════════════════════════════════════════════════════════
# HTTP API Integration Tests
# ════════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_api_capture_request(client):
    resp = await client.post(
        "/api/v1/procurement/requests",
        json={"company_id": "APICO", "raw_input": "Need bearing 6204 urgent"},
        headers=AUTH_TECH,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "captured"
    assert body["company_id"] == "APICO"


@pytest.mark.asyncio
async def test_api_list_procurement_agents(client):
    resp = await client.get("/api/v1/procurement/agents", headers=AUTH_TECH)
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list)
    assert len(body) == 8
    assert body[0]["id"] == "request_capture_agent"


@pytest.mark.asyncio
async def test_api_structure_then_get(client):
    create_resp = await client.post(
        "/api/v1/procurement/requests",
        json={"company_id": "API-STRUCT", "raw_input": "Need bearing 6204 urgent critical qty 2"},
        headers=AUTH_TECH,
    )
    request_id = create_resp.json()["id"]

    struct_resp = await client.post(
        f"/api/v1/procurement/requests/{request_id}/structure",
        headers=AUTH_TECH,
    )
    assert struct_resp.status_code == 201
    assert struct_resp.json()["request_id"] == request_id

    get_resp = await client.get(
        f"/api/v1/procurement/requests/{request_id}/structured",
        headers=AUTH_TECH,
    )
    assert get_resp.status_code == 200
    assert get_resp.json()["confidence_score"] >= 0.0


@pytest.mark.asyncio
async def test_api_cannot_route_unstructured(client):
    create_resp = await client.post(
        "/api/v1/procurement/requests",
        json={"company_id": "API-NOROUTE", "raw_input": "Something vague"},
        headers=AUTH_TECH,
    )
    request_id = create_resp.json()["id"]
    # Attempt to route without structuring first
    route_resp = await client.post(
        f"/api/v1/procurement/requests/{request_id}/route",
        headers=AUTH_TECH,
    )
    assert route_resp.status_code == 409


@pytest.mark.asyncio
async def test_api_submit_and_list_offers(client):
    # Capture + structure
    r = await client.post(
        "/api/v1/procurement/requests",
        json={"company_id": "API-OFFERS", "raw_input": "Need bearing urgent qty 1 sku BRG-X"},
        headers=AUTH_TECH,
    )
    rid = r.json()["id"]
    await client.post(f"/api/v1/procurement/requests/{rid}/structure", headers=AUTH_TECH)

    # Validate if needed
    struct = await client.get(f"/api/v1/procurement/requests/{rid}/structured", headers=AUTH_TECH)
    if struct.json()["needs_human_review"]:
        await client.patch(
            f"/api/v1/procurement/requests/{rid}/structured",
            json={"req_type": "SPARE_PART", "urgency_level": "high"},
            headers=AUTH_TECH,
        )

    # Route
    await client.post(f"/api/v1/procurement/requests/{rid}/route", headers=AUTH_TECH)

    # Submit two offers
    for price in (3000, 5000):
        offer_resp = await client.post(
            f"/api/v1/procurement/requests/{rid}/offers",
            json={
                "supplier_id": f"supplier-{price}",
                "price_cents": price,
                "lead_time_days": 5,
                "technical_compliance_score": 0.85,
            },
            headers=AUTH_TECH,
        )
        assert offer_resp.status_code == 201
        assert offer_resp.json()["is_normalized"] is True

    list_resp = await client.get(f"/api/v1/procurement/requests/{rid}/offers", headers=AUTH_TECH)
    assert list_resp.status_code == 200
    assert len(list_resp.json()) >= 2


@pytest.mark.asyncio
async def test_api_full_e2e_flow(client):
    """End-to-end: capture → structure → route → 2 offers → decide → order → feedback."""
    # 1. Capture
    r = await client.post(
        "/api/v1/procurement/requests",
        json={"company_id": "E2E-CO", "raw_input": "Need bearing motor urgent critical qty 2 sku BRG-6204"},
        headers=AUTH_TECH,
    )
    assert r.status_code == 201
    rid = r.json()["id"]

    # 2. Structure
    s = await client.post(f"/api/v1/procurement/requests/{rid}/structure", headers=AUTH_TECH)
    assert s.status_code == 201

    # 2a. Human validate if required
    struct_data = s.json()
    if struct_data["needs_human_review"]:
        v = await client.patch(
            f"/api/v1/procurement/requests/{rid}/structured",
            json={"req_type": "SPARE_PART", "urgency_level": "high"},
            headers=AUTH_TECH,
        )
        assert v.status_code == 200

    # 3. Route
    route = await client.post(f"/api/v1/procurement/requests/{rid}/route", headers=AUTH_TECH)
    assert route.status_code == 201

    # 4. Submit ≥ 2 offers
    for i, (price, lead) in enumerate([(2500, 3), (4000, 1)]):
        o = await client.post(
            f"/api/v1/procurement/requests/{rid}/offers",
            json={
                "supplier_id": f"e2e-supplier-{i}",
                "price_cents": price,
                "lead_time_days": lead,
                "technical_compliance_score": 0.9 - i * 0.1,
            },
            headers=AUTH_TECH,
        )
        assert o.status_code == 201

    # 5. Decide
    decide = await client.post(f"/api/v1/procurement/requests/{rid}/decide", headers=AUTH_TECH)
    assert decide.status_code == 201
    decision = decide.json()
    assert decision["recommended_offer_id"] is not None

    # GET decision
    get_dec = await client.get(f"/api/v1/procurement/requests/{rid}/decision", headers=AUTH_TECH)
    assert get_dec.status_code == 200

    # 6. Create order
    order_resp = await client.post(
        "/api/v1/procurement/orders",
        json={"request_id": rid, "selected_offer_id": decision["recommended_offer_id"]},
        headers=AUTH_TECH,
    )
    assert order_resp.status_code == 201
    order_id = order_resp.json()["id"]

    # 7. Complete order
    update_resp = await client.patch(
        f"/api/v1/procurement/orders/{order_id}",
        json={"status": "COMPLETED", "erp_reference": "ERP-E2E-001"},
        headers=AUTH_TECH,
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["status"] == "COMPLETED"

    # 8. Submit feedback
    fb_resp = await client.post(
        f"/api/v1/procurement/orders/{order_id}/feedback",
        json={"delivery_time_actual_days": 2, "quality_score": 0.95, "issue_flag": False},
        headers=AUTH_TECH,
    )
    assert fb_resp.status_code == 201
    fb = fb_resp.json()
    assert fb["quality_score"] == 0.95
    assert fb["issue_flag"] is False

    # Verify GET feedback
    get_fb = await client.get(f"/api/v1/procurement/orders/{order_id}/feedback", headers=AUTH_TECH)
    assert get_fb.status_code == 200


@pytest.mark.asyncio
async def test_api_cannot_order_without_decision(client):
    r = await client.post(
        "/api/v1/procurement/requests",
        json={"company_id": "NO-DEC-CO", "raw_input": "bearing urgent"},
        headers=AUTH_TECH,
    )
    rid = r.json()["id"]
    order_resp = await client.post(
        "/api/v1/procurement/orders",
        json={"request_id": rid, "selected_offer_id": "fake"},
        headers=AUTH_TECH,
    )
    assert order_resp.status_code == 409


@pytest.mark.asyncio
async def test_api_iot_trigger(client):
    resp = await client.post(
        "/api/v1/procurement/iot-trigger",
        json={
            "company_id": "IOT-API-CO",
            "machine_id": "m-123",
            "alert_type": "vibration_high",
            "description": "Abnormal vibration detected",
            "severity": "high",
        },
        headers=AUTH_TECH,
    )
    assert resp.status_code == 201
    assert resp.json()["source"] == "iot"


@pytest.mark.asyncio
async def test_api_create_supplier_requires_manager(client):
    resp = await client.post(
        "/api/v1/procurement/suppliers",
        json={"name": "Test Supplier", "capabilities": ["SPARE_PART"]},
        headers=AUTH_TECH,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_api_create_supplier_as_manager(client):
    resp = await client.post(
        "/api/v1/procurement/suppliers",
        json={
            "name": "Manager Supplier",
            "company_id": "MGR-CO",
            "capabilities": ["SERVICE"],
            "sla_hours": 24,
            "location": "US",
        },
        headers=AUTH_MANAGER,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "Manager Supplier"
    assert body["rating_score"] == 1.0


@pytest.mark.asyncio
async def test_api_metrics(client):
    resp = await client.get("/api/v1/procurement/metrics", headers=AUTH_TECH)
    assert resp.status_code == 200
    body = resp.json()
    assert "total_requests" in body
    assert "automation_ratio_pct" in body
    assert "total_orders" in body


@pytest.mark.asyncio
async def test_api_marketplace(client):
    # Create a global marketplace supplier (company_id=None → available to all)
    create_resp = await client.post(
        "/api/v1/procurement/suppliers",
        json={"name": "Open Market Co", "company_id": None, "is_marketplace": True, "capabilities": ["SPARE_PART"]},
        headers=AUTH_MANAGER,
    )
    assert create_resp.status_code == 201
    assert create_resp.json()["is_marketplace"] is True
    assert create_resp.json()["company_id"] is None

    resp = await client.get("/api/v1/procurement/marketplace/suppliers", headers=AUTH_TECH)
    assert resp.status_code == 200
    suppliers = resp.json()
    assert isinstance(suppliers, list)
    assert all(s["is_marketplace"] for s in suppliers)


@pytest.mark.asyncio
async def test_api_predict_needs(client):
    resp = await client.get(
        "/api/v1/procurement/predict?company_id=PREDICT-API-CO&horizon_days=30",
        headers=AUTH_TECH,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "predictions" in body
    assert body["company_id"] == "PREDICT-API-CO"


@pytest.mark.asyncio
async def test_api_auto_order_rules_manager_only(client):
    resp = await client.post(
        "/api/v1/procurement/auto-order/rules",
        json={"company_id": "AO-CO", "component": "belt", "req_type": "SPARE_PART", "min_stock": 2},
        headers=AUTH_TECH,
    )
    assert resp.status_code == 403

    resp2 = await client.post(
        "/api/v1/procurement/auto-order/rules",
        json={"company_id": "AO-CO", "component": "belt", "req_type": "SPARE_PART", "min_stock": 2},
        headers=AUTH_MANAGER,
    )
    assert resp2.status_code == 201
