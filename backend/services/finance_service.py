"""
Finance Service — pricing engine, contract management, invoice generation,
ERP export hook.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import List, Optional
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.core.events import Topics, get_event_bus
from backend.models.invoice import (
    Contract,
    ContractCreate,
    ContractStatus,
    Invoice,
    InvoiceCreate,
    InvoiceLineItem,
    InvoiceStatus,
    LineItemIn,
    PricingModel,
)

logger = logging.getLogger(__name__)

_contract_counter = 5000
_invoice_counter  = 9000

TAX_RATE = 0.10  # 10%


def _next_contract_number() -> str:
    global _contract_counter
    _contract_counter += 1
    return f"CTR-{_contract_counter:06d}"


def _next_invoice_number() -> str:
    global _invoice_counter
    _invoice_counter += 1
    return f"INV-{_invoice_counter:06d}"


# ── Pricing engine ─────────────────────────────────────────────────────────────
def calculate_price(
    pricing_model: PricingModel,
    base_fee_cents: int,
    usage_units: float = 0,
    unit_rate_cents: int = 0,
    performance_bonus_pct: float = 0,
) -> int:
    """Return total price in cents."""
    if pricing_model == PricingModel.FIXED:
        return base_fee_cents
    if pricing_model == PricingModel.USAGE_BASED:
        return base_fee_cents + int(usage_units * unit_rate_cents)
    if pricing_model == PricingModel.SUBSCRIPTION:
        return base_fee_cents
    if pricing_model == PricingModel.PERFORMANCE:
        bonus = int(base_fee_cents * performance_bonus_pct / 100)
        return base_fee_cents + bonus
    return base_fee_cents


# ── Contract management ────────────────────────────────────────────────────────
async def create_contract(db: AsyncSession, data: ContractCreate) -> Contract:
    contract = Contract(
        company_id=data.company_id,
        contract_number=_next_contract_number(),
        title=data.title,
        pricing_model=data.pricing_model,
        start_date=data.start_date,
        end_date=data.end_date,
        value_cents=data.value_cents,
        monthly_fee_cents=data.monthly_fee_cents,
        sla_uptime_pct=data.sla_uptime_pct,
        sla_response_hours=data.sla_response_hours,
        notes=data.notes,
        status=ContractStatus.DRAFT,
    )
    db.add(contract)
    await db.flush()
    logger.info("Created contract %s for company %s", contract.contract_number, data.company_id)
    return contract


async def get_contract(db: AsyncSession, contract_id: str) -> Optional[Contract]:
    result = await db.execute(
        select(Contract).options(selectinload(Contract.invoices)).where(Contract.id == contract_id)
    )
    return result.scalar_one_or_none()


async def list_contracts(
    db: AsyncSession, company_id: Optional[str] = None, limit: int = 50
) -> List[Contract]:
    q = select(Contract)
    if company_id:
        q = q.where(Contract.company_id == company_id)
    q = q.order_by(Contract.created_at.desc()).limit(limit)
    result = await db.execute(q)
    return list(result.scalars().all())


async def refresh_contract_statuses(db: AsyncSession) -> int:
    """Update ACTIVE → EXPIRING or EXPIRED based on end_date. Returns count updated."""
    today = date.today()
    from sqlalchemy import update as sa_update
    # Expired
    stmt = (
        sa_update(Contract)
        .where(Contract.status == ContractStatus.ACTIVE, Contract.end_date < today)
        .values(status=ContractStatus.EXPIRED)
    )
    result = await db.execute(stmt)
    expired = result.rowcount

    # Expiring in next 30 days
    from datetime import timedelta
    cutoff = today + timedelta(days=30)
    stmt2 = (
        sa_update(Contract)
        .where(
            Contract.status == ContractStatus.ACTIVE,
            Contract.end_date.between(today, cutoff),
        )
        .values(status=ContractStatus.EXPIRING)
    )
    result2 = await db.execute(stmt2)
    return expired + result2.rowcount


# ── Invoice generation ─────────────────────────────────────────────────────────
async def create_invoice(db: AsyncSession, data: InvoiceCreate) -> Invoice:
    subtotal = sum(
        int(item.quantity * item.unit_price_cents) for item in data.line_items
    )
    tax = int(subtotal * TAX_RATE)
    total = subtotal + tax

    invoice = Invoice(
        company_id=data.company_id,
        contract_id=data.contract_id,
        invoice_number=_next_invoice_number(),
        issue_date=data.issue_date or date.today(),
        due_date=data.due_date,
        currency=data.currency,
        notes=data.notes,
        subtotal_cents=subtotal,
        tax_cents=tax,
        total_cents=total,
    )
    db.add(invoice)
    await db.flush()

    for item in data.line_items:
        li = InvoiceLineItem(
            invoice_id=invoice.id,
            description=item.description,
            quantity=item.quantity,
            unit_price_cents=item.unit_price_cents,
            total_cents=int(item.quantity * item.unit_price_cents),
            source_type=item.source_type,
            source_id=item.source_id,
        )
        db.add(li)

    await db.flush()

    bus = get_event_bus()
    await bus.publish(Topics.INVOICE_GENERATED, {
        "invoice_id":     invoice.id,
        "invoice_number": invoice.invoice_number,
        "company_id":     invoice.company_id,
        "total_cents":    total,
    }, source="finance")

    logger.info("Invoice %s generated for company %s (total: $%.2f)", invoice.invoice_number, data.company_id, total / 100)
    return invoice


async def generate_invoice_from_work_order(
    db: AsyncSession,
    company_id: str,
    work_order_id: str,
    actual_cost_cents: int,
    contract_id: Optional[str] = None,
) -> Invoice:
    """Auto-generate an invoice from a completed work order."""
    line_items = [
        LineItemIn(
            description=f"Service — Work Order {work_order_id}",
            quantity=1.0,
            unit_price_cents=actual_cost_cents,
            source_type="work_order",
            source_id=work_order_id,
        )
    ]
    invoice = await create_invoice(db, InvoiceCreate(
        company_id=company_id,
        contract_id=contract_id,
        line_items=line_items,
    ))
    # Re-fetch with eager-loaded relationships
    return await get_invoice(db, invoice.id)


async def get_invoice(db: AsyncSession, invoice_id: str) -> Optional[Invoice]:
    result = await db.execute(
        select(Invoice)
        .options(selectinload(Invoice.line_items))
        .where(Invoice.id == invoice_id)
    )
    return result.scalar_one_or_none()


async def list_invoices(
    db: AsyncSession, company_id: Optional[str] = None, limit: int = 50
) -> List[Invoice]:
    q = select(Invoice).options(selectinload(Invoice.line_items))
    if company_id:
        q = q.where(Invoice.company_id == company_id)
    q = q.order_by(Invoice.created_at.desc()).limit(limit)
    result = await db.execute(q)
    return list(result.scalars().all())


async def export_invoice_to_erp(db: AsyncSession, invoice_id: str) -> dict:
    """Stub: export invoice payload to external ERP system."""
    invoice = await get_invoice(db, invoice_id)
    if invoice is None:
        raise ValueError(f"Invoice {invoice_id} not found")
    # In production: call ERP REST API / SAP BAPI here
    payload = {
        "erp_document_type": "AR",
        "invoice_number":    invoice.invoice_number,
        "company_id":        invoice.company_id,
        "total_cents":       invoice.total_cents,
        "currency":          invoice.currency,
        "exported_at":       datetime.now(tz=timezone.utc).isoformat(),
    }
    invoice.erp_exported = True
    await db.flush()
    logger.info("Invoice %s exported to ERP (stub)", invoice.invoice_number)
    return payload
