"""
External client registry and ingestion endpoints.
"""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from backend.core.security import get_current_user_payload
from backend.models.external_integration import (
    ClientStatus,
    ExternalClientCreate,
    ExternalClientOut,
    ExternalIngestionPayloadIn,
    ExternalIngestionResult,
    NormalizedEventOut,
    NormalizedRequestOut,
)
from backend.services import external_integration_service

router = APIRouter(prefix="/external", tags=["External Integration"])


@router.post("/clients", response_model=ExternalClientOut, status_code=status.HTTP_201_CREATED)
async def create_client(
    data: ExternalClientCreate,
    _auth: dict = Depends(get_current_user_payload),
    db: AsyncSession = Depends(get_db),
):
    client = await external_integration_service.create_client(db, data)
    return ExternalClientOut.model_validate(client)


@router.get("/clients", response_model=List[ExternalClientOut])
async def list_clients(
    status: Optional[ClientStatus] = Query(None),
    _auth: dict = Depends(get_current_user_payload),
    db: AsyncSession = Depends(get_db),
):
    clients = await external_integration_service.list_clients(db, status=status)
    return [ExternalClientOut.model_validate(c) for c in clients]


@router.post("/ingest/{client_id}", response_model=ExternalIngestionResult)
async def ingest_payload(
    client_id: str,
    payload: ExternalIngestionPayloadIn,
    _auth: dict = Depends(get_current_user_payload),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await external_integration_service.ingest_payload(db, client_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return result


@router.post("/poll/{client_id}", response_model=ExternalIngestionResult)
async def poll_simulator(
    client_id: str,
    _auth: dict = Depends(get_current_user_payload),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await external_integration_service.poll_factory_simulator(db, client_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Factory simulator polling failed: {exc}") from exc
    return result


@router.get("/events", response_model=List[NormalizedEventOut])
async def list_events(
    client_id: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    _auth: dict = Depends(get_current_user_payload),
    db: AsyncSession = Depends(get_db),
):
    events = await external_integration_service.list_normalized_events(db, client_id=client_id, limit=limit)
    return [NormalizedEventOut.model_validate(e) for e in events]


@router.get("/requests", response_model=List[NormalizedRequestOut])
async def list_requests(
    client_id: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    _auth: dict = Depends(get_current_user_payload),
    db: AsyncSession = Depends(get_db),
):
    requests = await external_integration_service.list_normalized_requests(db, client_id=client_id, limit=limit)
    return [NormalizedRequestOut.model_validate(r) for r in requests]
