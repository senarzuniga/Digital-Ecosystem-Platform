"""
External data source integration:
- client registry
- polling intake
- normalization
- integration with alerts/workflow/procurement
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.connectors.rest_connector import RestConnector
from backend.core.config import get_settings
from backend.models.alert import AlertCategory, AlertCreate, AlertSeverity
from backend.models.external_integration import (
    ClientStatus,
    ClientType,
    ConnectionType,
    ExternalClient,
    ExternalClientCreate,
    ExternalIngestionPayloadIn,
    ExternalIngestionResult,
    NormalizedEvent,
    NormalizedRequest,
)
from backend.models.procurement import IoTTriggerIn
from backend.models.workflow import WorkflowCreate, WorkflowTriggerType
from backend.services import alert_service, procurement_service, workflow_service

logger = logging.getLogger(__name__)
settings = get_settings()


def _safe_dt(value: object) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str) and value.strip():
        text = value.strip().replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(text)
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    return datetime.now(tz=timezone.utc)


def _norm_event_severity(value: Optional[str]) -> str:
    sev = (value or "info").lower()
    if sev in {"critical", "high", "warning", "info"}:
        return sev
    if sev in {"error", "fatal"}:
        return "critical"
    if sev in {"warn", "medium"}:
        return "warning"
    if sev in {"low", "ok"}:
        return "info"
    return "info"


def _severity_to_alert(value: str) -> AlertSeverity:
    if value == "critical":
        return AlertSeverity.CRITICAL
    if value == "high":
        return AlertSeverity.HIGH
    if value == "warning":
        return AlertSeverity.WARNING
    return AlertSeverity.INFO


def _norm_urgency(value: Optional[str]) -> str:
    urgency = (value or "medium").lower()
    if urgency in {"critical", "high", "medium", "low"}:
        return urgency
    if urgency in {"warning", "warn"}:
        return "medium"
    if urgency in {"info", "ok"}:
        return "low"
    if urgency in {"error", "fatal"}:
        return "critical"
    return "medium"


async def ensure_default_factory_simulator_client(db: AsyncSession) -> ExternalClient:
    result = await db.execute(select(ExternalClient).where(ExternalClient.id == "digital_factory_1"))
    client = result.scalar_one_or_none()
    if client is not None:
        return client

    client = ExternalClient(
        id="digital_factory_1",
        name="Factory-Simulator",
        type=ClientType.SIMULATED,
        api_endpoint=settings.FACTORY_SIMULATOR_URL,
        connection_type=ConnectionType.REST,
        status=ClientStatus.ACTIVE,
    )
    db.add(client)
    await db.flush()
    logger.info("Default simulated client registered: %s", client.id)
    return client


async def create_client(db: AsyncSession, data: ExternalClientCreate) -> ExternalClient:
    existing = await get_client(db, data.id)
    if existing:
        return existing
    client = ExternalClient(**data.model_dump())
    db.add(client)
    await db.flush()
    return client


async def get_client(db: AsyncSession, client_id: str) -> Optional[ExternalClient]:
    result = await db.execute(select(ExternalClient).where(ExternalClient.id == client_id))
    return result.scalar_one_or_none()


async def list_clients(
    db: AsyncSession, status: Optional[ClientStatus] = None
) -> List[ExternalClient]:
    q = select(ExternalClient).order_by(ExternalClient.name.asc())
    if status:
        q = q.where(ExternalClient.status == status)
    result = await db.execute(q)
    return list(result.scalars().all())


def normalize_event(client_id: str, raw: Dict) -> NormalizedEvent:
    event_type = str(raw.get("type") or raw.get("event_type") or raw.get("category") or "unknown")
    asset_id = raw.get("asset_id") or raw.get("machine_id") or raw.get("machine") or raw.get("line_id")
    severity = _norm_event_severity(raw.get("severity") or raw.get("priority") or raw.get("level"))
    description = str(raw.get("description") or raw.get("message") or raw.get("details") or event_type)
    ts = _safe_dt(raw.get("timestamp") or raw.get("time") or raw.get("created_at"))
    source_event_id = str(raw.get("id")) if raw.get("id") else None
    normalized_id = source_event_id or f"evt-{uuid4()}"
    return NormalizedEvent(
        id=normalized_id,
        client_id=client_id,
        type=event_type,
        asset_id=str(asset_id) if asset_id is not None else None,
        severity=severity,
        description=description,
        timestamp=ts,
        source_event_id=source_event_id,
        raw_payload=json.dumps(raw),
    )


def normalize_request(client_id: str, raw: Dict) -> NormalizedRequest:
    req_type = str(raw.get("type") or raw.get("request_type") or raw.get("need_type") or "unknown")
    urgency = _norm_urgency(raw.get("urgency") or raw.get("priority") or raw.get("severity") or "medium")
    status = str(raw.get("status") or "new")
    source_request_id = str(raw.get("id")) if raw.get("id") else None
    normalized_id = source_request_id or f"req-{uuid4()}"
    structured = raw.get("structured_data")
    structured_data = structured if isinstance(structured, dict) else raw
    return NormalizedRequest(
        id=normalized_id,
        client_id=client_id,
        type=req_type,
        structured_data=json.dumps(structured_data),
        urgency=urgency,
        status=status,
        source_request_id=source_request_id,
    )


async def _integrate_normalized_event(
    db: AsyncSession, event: NormalizedEvent
) -> tuple[int, int]:
    alerts_created = 0
    workflows_started = 0

    if event.severity in {"critical", "high"}:
        alert = await alert_service.create_alert(
            db,
            AlertCreate(
                company_id=event.client_id,
                asset_id=None,
                severity=_severity_to_alert(event.severity),
                category=AlertCategory.OPERATIONAL,
                title=f"[External] {event.type}",
                description=event.description,
                source="external_ingestion",
            ),
            auto_respond=True,
        )
        alerts_created += 1

        wf = await workflow_service.create_workflow(
            db,
            WorkflowCreate(
                idempotency_key=f"external-event-{event.id}",
                company_id=event.client_id,
                trigger_type=WorkflowTriggerType.ALERT,
                trigger_id=alert.id,
                title=f"External event workflow · {event.type}",
                description=event.description,
            ),
            created_by="external_ingestion",
        )
        await workflow_service.execute_workflow(db, wf.id)
        workflows_started += 1

    return alerts_created, workflows_started


async def _integrate_normalized_request(
    db: AsyncSession, req: NormalizedRequest
) -> tuple[int, int]:
    procurement_requests_created = 0
    workflows_started = 0

    structured = req.get_structured_data()
    machine_id = str(structured.get("asset_id") or structured.get("machine_id") or "external-asset")
    desc = str(structured.get("description") or structured.get("message") or req.type)

    procurement_req = await procurement_service.iot_trigger(
        db,
        IoTTriggerIn(
            company_id=req.client_id,
            machine_id=machine_id,
            asset_id=None,
            alert_type=req.type,
            description=desc,
            severity=req.urgency,
        ),
    )
    req.procurement_request_id = procurement_req.id
    procurement_requests_created += 1

    wf = await workflow_service.create_workflow(
        db,
        WorkflowCreate(
            idempotency_key=f"external-request-{req.id}",
            company_id=req.client_id,
            trigger_type=WorkflowTriggerType.MANUAL,
            title=f"External request workflow · {req.type}",
            description=desc,
        ),
        created_by="external_ingestion",
    )
    await workflow_service.execute_workflow(db, wf.id)
    workflows_started += 1
    return procurement_requests_created, workflows_started


async def ingest_payload(
    db: AsyncSession,
    client_id: str,
    payload: ExternalIngestionPayloadIn,
) -> ExternalIngestionResult:
    client = await get_client(db, client_id)
    if client is None:
        raise ValueError(f"External client '{client_id}' not found")

    alerts_created = 0
    workflows_started = 0
    procurement_requests_created = 0
    events_ingested = 0
    requests_ingested = 0

    for raw_event in payload.events:
        event = normalize_event(client_id, raw_event)
        db.add(event)
        await db.flush()
        events_ingested += 1
        a, w = await _integrate_normalized_event(db, event)
        alerts_created += a
        workflows_started += w

    for raw_req in payload.requests:
        req = normalize_request(client_id, raw_req)
        db.add(req)
        await db.flush()
        requests_ingested += 1
        p, w = await _integrate_normalized_request(db, req)
        procurement_requests_created += p
        workflows_started += w

    return ExternalIngestionResult(
        client_id=client_id,
        events_ingested=events_ingested,
        requests_ingested=requests_ingested,
        alerts_created=alerts_created,
        workflows_started=workflows_started,
        procurement_requests_created=procurement_requests_created,
    )


async def poll_factory_simulator(db: AsyncSession, client_id: str) -> ExternalIngestionResult:
    client = await get_client(db, client_id)
    if client is None:
        raise ValueError(f"External client '{client_id}' not found")
    if client.connection_type != ConnectionType.REST:
        raise ValueError("Only REST polling is implemented for this client")

    async with RestConnector(base_url=client.api_endpoint) as connector:
        events = await connector.get("/factory/events")
        requests = await connector.get("/factory/requests")

    payload = ExternalIngestionPayloadIn(
        events=events if isinstance(events, list) else [],
        requests=requests if isinstance(requests, list) else [],
    )
    return await ingest_payload(db, client_id, payload)


async def list_normalized_events(
    db: AsyncSession,
    client_id: Optional[str] = None,
    limit: int = 100,
) -> List[NormalizedEvent]:
    q = select(NormalizedEvent).order_by(NormalizedEvent.timestamp.desc()).limit(limit)
    if client_id:
        q = q.where(NormalizedEvent.client_id == client_id)
    result = await db.execute(q)
    return list(result.scalars().all())


async def list_normalized_requests(
    db: AsyncSession,
    client_id: Optional[str] = None,
    limit: int = 100,
) -> List[NormalizedRequest]:
    q = select(NormalizedRequest).order_by(NormalizedRequest.created_at.desc()).limit(limit)
    if client_id:
        q = q.where(NormalizedRequest.client_id == client_id)
    result = await db.execute(q)
    return list(result.scalars().all())
