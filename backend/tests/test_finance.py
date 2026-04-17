"""
Tests for Finance service.
"""

import pytest
from datetime import date

from backend.models.invoice import ContractCreate, InvoiceCreate, LineItemIn, PricingModel
from backend.services import finance_service


@pytest.mark.asyncio
async def test_create_contract(db):
    data = ContractCreate(
        company_id="ACME",
        title="Annual Service Contract",
        pricing_model=PricingModel.SUBSCRIPTION,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 31),
        monthly_fee_cents=500000,
    )
    contract = await finance_service.create_contract(db, data)
    assert contract.id is not None
    assert contract.contract_number.startswith("CTR-")


@pytest.mark.asyncio
async def test_create_invoice_with_line_items(db):
    data = InvoiceCreate(
        company_id="ACME",
        currency="USD",
        line_items=[
            LineItemIn(description="Labour 4h", quantity=4.0, unit_price_cents=7500),
            LineItemIn(description="Bearing replacement", quantity=1.0, unit_price_cents=25000),
        ],
    )
    invoice = await finance_service.create_invoice(db, data)
    assert invoice.invoice_number.startswith("INV-")
    expected_subtotal = (4 * 7500) + (1 * 25000)  # 55000
    assert invoice.subtotal_cents == expected_subtotal
    assert invoice.tax_cents == int(expected_subtotal * 0.10)
    assert invoice.total_cents == invoice.subtotal_cents + invoice.tax_cents


@pytest.mark.asyncio
async def test_generate_invoice_from_wo(db):
    invoice = await finance_service.generate_invoice_from_work_order(
        db, company_id="ACME", work_order_id="wo-001", actual_cost_cents=150000
    )
    assert invoice.total_cents > 0
    items = invoice.line_items
    assert len(items) == 1
    assert "wo-001" in items[0].source_id


@pytest.mark.asyncio
async def test_pricing_engine_fixed(db):
    total = finance_service.calculate_price(PricingModel.FIXED, base_fee_cents=100000)
    assert total == 100000


@pytest.mark.asyncio
async def test_pricing_engine_usage_based(db):
    total = finance_service.calculate_price(
        PricingModel.USAGE_BASED,
        base_fee_cents=10000,
        usage_units=100,
        unit_rate_cents=50,
    )
    assert total == 10000 + 100 * 50  # 15000


@pytest.mark.asyncio
async def test_erp_export(db):
    inv = await finance_service.generate_invoice_from_work_order(
        db, company_id="ACME", work_order_id="wo-erp", actual_cost_cents=20000
    )
    result = await finance_service.export_invoice_to_erp(db, inv.id)
    assert result["erp_document_type"] == "AR"
    assert result["invoice_number"] == inv.invoice_number


@pytest.mark.asyncio
async def test_list_invoices(db):
    for _ in range(3):
        await finance_service.generate_invoice_from_work_order(
            db, company_id="LIST-ACME", work_order_id="wo-x", actual_cost_cents=1000
        )
    invoices = await finance_service.list_invoices(db, company_id="LIST-ACME")
    assert len(invoices) >= 3
