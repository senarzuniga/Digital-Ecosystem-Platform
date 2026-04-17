"""
Finance router — contracts and invoices.
"""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from backend.core.security import Role, get_current_user_payload, require_roles
from backend.models.invoice import ContractCreate, ContractOut, InvoiceCreate, InvoiceOut
from backend.services import finance_service

router = APIRouter(prefix="/finance", tags=["Finance"])


# ── Contracts ─────────────────────────────────────────────────────────────────
@router.post("/contracts", response_model=ContractOut, status_code=201)
async def create_contract(
    data: ContractCreate,
    _auth: dict = Depends(require_roles(Role.ADMIN, Role.MANAGER)),
    db: AsyncSession = Depends(get_db),
):
    c = await finance_service.create_contract(db, data)
    return ContractOut.model_validate(c)


@router.get("/contracts", response_model=List[ContractOut])
async def list_contracts(
    company_id: Optional[str] = Query(None),
    _auth: dict = Depends(get_current_user_payload),
    db: AsyncSession = Depends(get_db),
):
    contracts = await finance_service.list_contracts(db, company_id=company_id)
    return [ContractOut.model_validate(c) for c in contracts]


@router.get("/contracts/{contract_id}", response_model=ContractOut)
async def get_contract(
    contract_id: str,
    _auth: dict = Depends(get_current_user_payload),
    db: AsyncSession = Depends(get_db),
):
    c = await finance_service.get_contract(db, contract_id)
    if c is None:
        raise HTTPException(status_code=404, detail="Contract not found")
    return ContractOut.model_validate(c)


@router.post("/contracts/refresh-statuses")
async def refresh_contract_statuses(
    _auth: dict = Depends(require_roles(Role.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    updated = await finance_service.refresh_contract_statuses(db)
    return {"contracts_updated": updated}


# ── Invoices ──────────────────────────────────────────────────────────────────
@router.post("/invoices", response_model=InvoiceOut, status_code=201)
async def create_invoice(
    data: InvoiceCreate,
    _auth: dict = Depends(require_roles(Role.ADMIN, Role.MANAGER)),
    db: AsyncSession = Depends(get_db),
):
    inv = await finance_service.create_invoice(db, data)
    return InvoiceOut.model_validate(inv)


@router.get("/invoices", response_model=List[InvoiceOut])
async def list_invoices(
    company_id: Optional[str] = Query(None),
    _auth: dict = Depends(get_current_user_payload),
    db: AsyncSession = Depends(get_db),
):
    invoices = await finance_service.list_invoices(db, company_id=company_id)
    return [InvoiceOut.model_validate(i) for i in invoices]


@router.get("/invoices/{invoice_id}", response_model=InvoiceOut)
async def get_invoice(
    invoice_id: str,
    _auth: dict = Depends(get_current_user_payload),
    db: AsyncSession = Depends(get_db),
):
    inv = await finance_service.get_invoice(db, invoice_id)
    if inv is None:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return InvoiceOut.model_validate(inv)


@router.post("/invoices/{invoice_id}/export-erp")
async def export_invoice(
    invoice_id: str,
    _auth: dict = Depends(require_roles(Role.ADMIN, Role.MANAGER)),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await finance_service.export_invoice_to_erp(db, invoice_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
