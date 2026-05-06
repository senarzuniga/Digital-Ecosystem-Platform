"""
External data source integration:
- client registry
- background polling intake
- normalization
- integration with alerts/workflow/procurement
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.connectors.rest_connector import RestConnector
from backend.core.config import get_settings
from backend.core.database import AsyncSessionLocal
from backend.core.events import Topics, get_event_bus
from backend.models.alert import AlertCategory, AlertCreate, AlertSeverity
from backend.models.external_integration import (
    ClientStatus,
    ClientType,
    ConnectionType,
    ExternalClient,
    ExternalClientCreate,
    ExternalClientOut,
    ExternalClientSyncState,
    ExternalClientUpdate,
    ExternalIngestionPayloadIn,
    ExternalIngestionResult,
    ExternalIngestionStatusOut,
    NormalizedEvent,
    NormalizedRequest,
)
from backend.models.procurement import IoTTriggerIn
from backend.models.workflow import WorkflowCreate, WorkflowTriggerType
from backend.services import alert_service, procurement_service, workflow_service

logger = logging.getLogger(__name__)
settings = get_settings()


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


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
    return _utcnow()


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


def _extract_list(payload: Any, keys: tuple[str, ...]) -> List[Dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in keys:
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    return []


async def _get_sync_state(
    db: AsyncSession,
    client_id: str,
    poll_interval_seconds: Optional[int] = None,
) -> ExternalClientSyncState:
    result = await db.execute(
        select(ExternalClientSyncState).where(ExternalClientSyncState.client_id == client_id)
    )
    state = result.scalar_one_or_none()
    if state is None:
        state = ExternalClientSyncState(
            client_id=client_id,
            poll_interval_seconds=max(1, poll_interval_seconds or settings.EXTERNAL_POLL_INTERVAL_SECONDS),
        )
        db.add(state)
        await db.flush()
        return state

    if poll_interval_seconds is not None:
        state.poll_interval_seconds = max(1, poll_interval_seconds)
    return state


async def _get_sync_state_map(
    db: AsyncSession,
    client_ids: List[str],
) -> Dict[str, ExternalClientSyncState]:
    if not client_ids:
        return {}

    result = await db.execute(
        select(ExternalClientSyncState).where(ExternalClientSyncState.client_id.in_(client_ids))
    )
    states = {state.client_id: state for state in result.scalars().all()}
    for client_id in client_ids:
        if client_id not in states:
            states[client_id] = await _get_sync_state(db, client_id)
    return states


def _serialize_client(
    client: ExternalClient,
    state: Optional[ExternalClientSyncState],
) -> ExternalClientOut:
    poll_interval = state.poll_interval_seconds if state else client.poll_interval_seconds
    return ExternalClientOut(
        id=client.id,
        name=client.name,
        company_id=client.company_id,
        type=client.type,
        api_endpoint=client.api_endpoint,
        connection_type=client.connection_type,
        status=client.status,
        poll_interval_seconds=poll_interval,
        last_polled_at=state.last_polled_at if state else None,
        last_seen_at=state.last_seen_at if state else None,
        last_error=state.last_error if state else None,
        consecutive_failures=state.consecutive_failures if state else 0,
        created_at=client.created_at,
        updated_at=client.updated_at,
    )


async def ensure_default_factory_simulator_client(db: AsyncSession) -> ExternalClient:
    result = await db.execute(
        select(ExternalClient).where(
            or_(
                ExternalClient.id == "digital_factory_1",
                ExternalClient.name == "Factory-Simulator",
            )
        )
    )
    client = result.scalar_one_or_none()
    if client is None:
        client = ExternalClient(
            id="digital_factory_1",
            name="Factory-Simulator",
            company_id="digital_factory_1",
            poll_interval_seconds=settings.EXTERNAL_POLL_INTERVAL_SECONDS,
            type=ClientType.SIMULATED,
            api_endpoint=settings.FACTORY_SIMULATOR_URL,
            connection_type=ConnectionType.REST,
            status=ClientStatus.ACTIVE,
        )
        db.add(client)
        await db.flush()
        logger.info("Default simulated client registered: %s", client.id)
    elif client.api_endpoint in {"http://localhost:9100", settings.FACTORY_SIMULATOR_URL}:
        client.api_endpoint = settings.FACTORY_SIMULATOR_URL

    if not client.company_id:
        client.company_id = "digital_factory_1"
    if not client.poll_interval_seconds:
        client.poll_interval_seconds = settings.EXTERNAL_POLL_INTERVAL_SECONDS

    if client.id != "digital_factory_1":
        logger.warning(
            "Factory-Simulator exists with id '%s' (expected 'digital_factory_1'). Reusing existing id.",
            client.id,
        )

    await _get_sync_state(db, client.id, client.poll_interval_seconds)
    return client


async def create_client(db: AsyncSession, data: ExternalClientCreate) -> ExternalClient:
    existing = await get_client(db, data.id)
    if existing:
        existing.poll_interval_seconds = max(1, data.poll_interval_seconds)
        await _get_sync_state(db, existing.id, existing.poll_interval_seconds)
        return existing

    payload = data.model_dump()
    poll_interval_seconds = payload.pop("poll_interval_seconds", settings.EXTERNAL_POLL_INTERVAL_SECONDS)
    payload["poll_interval_seconds"] = max(1, poll_interval_seconds)
    client = ExternalClient(**payload)
    db.add(client)
    await db.flush()
    await _get_sync_state(db, client.id, client.poll_interval_seconds)
    return client


async def update_client(
    db: AsyncSession,
    client_id: str,
    data: ExternalClientUpdate,
) -> Optional[ExternalClient]:
    client = await get_client(db, client_id)
    if client is None:
        return None

    updates = data.model_dump(exclude_none=True)
    poll_interval_seconds = updates.pop("poll_interval_seconds", None)
    for field_name, value in updates.items():
        setattr(client, field_name, value)

    if poll_interval_seconds is not None:
        client.poll_interval_seconds = max(1, poll_interval_seconds)

    await _get_sync_state(db, client.id, client.poll_interval_seconds)
    await db.flush()
    return client


async def get_client(db: AsyncSession, client_id: str) -> Optional[ExternalClient]:
    result = await db.execute(select(ExternalClient).where(ExternalClient.id == client_id))
    return result.scalar_one_or_none()


async def get_client_out(db: AsyncSession, client_id: str) -> Optional[ExternalClientOut]:
    client = await get_client(db, client_id)
    if client is None:
        return None
    state = await _get_sync_state(db, client_id)
    return _serialize_client(client, state)


async def list_clients(
    db: AsyncSession,
    status: Optional[ClientStatus] = None,
) -> List[ExternalClient]:
    query = select(ExternalClient).order_by(ExternalClient.name.asc())
    if status:
        query = query.where(ExternalClient.status == status)
    result = await db.execute(query)
    return list(result.scalars().all())


async def list_clients_out(
    db: AsyncSession,
    status: Optional[ClientStatus] = None,
) -> List[ExternalClientOut]:
    clients = await list_clients(db, status=status)
    state_map = await _get_sync_state_map(db, [client.id for client in clients])
    return [_serialize_client(client, state_map.get(client.id)) for client in clients]


def normalize_event(client_id: str, raw: Dict[str, Any]) -> NormalizedEvent:
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
        raw_payload=json.dumps(raw, default=str),
    )


def normalize_request(client_id: str, raw: Dict[str, Any]) -> NormalizedRequest:
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
        structured_data=json.dumps(structured_data, default=str),
        urgency=urgency,
        status=status,
        source_request_id=source_request_id,
    )


async def _event_exists(db: AsyncSession, event: NormalizedEvent) -> bool:
    if event.source_event_id:
        result = await db.execute(
            select(NormalizedEvent.id).where(
                NormalizedEvent.client_id == event.client_id,
                NormalizedEvent.source_event_id == event.source_event_id,
            )
        )
        return result.scalar_one_or_none() is not None

    result = await db.execute(
        select(NormalizedEvent.id).where(
            NormalizedEvent.client_id == event.client_id,
            NormalizedEvent.type == event.type,
            NormalizedEvent.description == event.description,
            NormalizedEvent.timestamp == event.timestamp,
        )
    )
    return result.scalar_one_or_none() is not None


async def _request_exists(db: AsyncSession, req: NormalizedRequest) -> bool:
    if req.source_request_id:
        result = await db.execute(
            select(NormalizedRequest.id).where(
                NormalizedRequest.client_id == req.client_id,
                NormalizedRequest.source_request_id == req.source_request_id,
            )
        )
        return result.scalar_one_or_none() is not None

    result = await db.execute(
        select(NormalizedRequest.id).where(
            NormalizedRequest.client_id == req.client_id,
            NormalizedRequest.type == req.type,
            NormalizedRequest.structured_data == req.structured_data,
            NormalizedRequest.status == req.status,
        )
    )
    return result.scalar_one_or_none() is not None


async def _integrate_normalized_event(
    db: AsyncSession,
    event: NormalizedEvent,
) -> tuple[int, int]:
    alerts_created = 0
    workflows_started = 0
    event_bus = get_event_bus()

    await event_bus.publish(
        Topics.EXTERNAL_EVENT_NORMALIZED,
        {
            "client_id": event.client_id,
            "event_id": event.id,
            "type": event.type,
            "severity": event.severity,
            "asset_id": event.asset_id,
        },
        source="external_ingestion",
    )

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

        workflow = await workflow_service.create_workflow(
            db,
            WorkflowCreate(
                idempotency_key=f"external-event-{event.id}",
                company_id=event.client_id,
                asset_id=None,
                trigger_type=WorkflowTriggerType.ALERT,
                trigger_id=alert.id,
                title=f"External event workflow · {event.type}",
                description=event.description,
            ),
            created_by="external_ingestion",
        )
        try:
            await workflow_service.execute_workflow(db, workflow.id)
            workflows_started += 1
        except Exception as exc:
            logger.warning("External event workflow execution failed for %s: %s", event.id, exc)

    return alerts_created, workflows_started


async def _integrate_normalized_request(
    db: AsyncSession,
    req: NormalizedRequest,
) -> tuple[int, int]:
    procurement_requests_created = 0
    workflows_started = 0
    event_bus = get_event_bus()

    structured = req.get_structured_data()
    machine_id = str(structured.get("asset_id") or structured.get("machine_id") or "external-asset")
    description = str(structured.get("description") or structured.get("message") or req.type)

    await event_bus.publish(
        Topics.EXTERNAL_REQUEST_NORMALIZED,
        {
            "client_id": req.client_id,
            "request_id": req.id,
            "type": req.type,
            "urgency": req.urgency,
        },
        source="external_ingestion",
    )

    procurement_req = await procurement_service.iot_trigger(
        db,
        IoTTriggerIn(
            company_id=req.client_id,
            machine_id=machine_id,
            asset_id=structured.get("asset_id"),
            alert_type=req.type,
            description=description,
            severity=req.urgency,
        ),
    )
    req.procurement_request_id = procurement_req.id
    procurement_requests_created += 1

    workflow = await workflow_service.create_workflow(
        db,
        WorkflowCreate(
            idempotency_key=f"external-request-{req.id}",
            company_id=req.client_id,
            asset_id=None,
            trigger_type=WorkflowTriggerType.EXTERNAL_REQUEST,
            trigger_id=procurement_req.id,
            title=f"External request workflow · {req.type}",
            description=description,
            requires_approval=req.urgency in {"high", "critical"},
        ),
        created_by="external_ingestion",
    )
    try:
        await workflow_service.execute_workflow(db, workflow.id)
        workflows_started += 1
    except Exception as exc:
        logger.warning("External request workflow execution failed for %s: %s", req.id, exc)

    await event_bus.publish(
        Topics.PROCUREMENT_REQUEST_DISPATCHED,
        {
            "client_id": req.client_id,
            "request_id": req.id,
            "procurement_request_id": procurement_req.id,
            "workflow_id": workflow.id,
        },
        source="external_ingestion",
    )

    return procurement_requests_created, workflows_started


async def ingest_payload(
    db: AsyncSession,
    client_id: str,
    payload: ExternalIngestionPayloadIn,
) -> ExternalIngestionResult:
    client = await get_client(db, client_id)
    if client is None:
        raise ValueError(f"External client '{client_id}' not found")

    state = await _get_sync_state(db, client_id)
    alerts_created = 0
    workflows_started = 0
    procurement_requests_created = 0
    events_ingested = 0
    requests_ingested = 0

    for raw_event in payload.events:
        event = normalize_event(client_id, raw_event)
        if await _event_exists(db, event):
            continue
        db.add(event)
        await db.flush()
        events_ingested += 1
        created_alerts, created_workflows = await _integrate_normalized_event(db, event)
        alerts_created += created_alerts
        workflows_started += created_workflows

    for raw_req in payload.requests:
        req = normalize_request(client_id, raw_req)
        if await _request_exists(db, req):
            continue
        db.add(req)
        await db.flush()
        requests_ingested += 1
        created_procurement, created_workflows = await _integrate_normalized_request(db, req)
        procurement_requests_created += created_procurement
        workflows_started += created_workflows

    client.status = ClientStatus.ACTIVE
    state.last_polled_at = _utcnow()
    if events_ingested or requests_ingested:
        state.last_seen_at = _utcnow()
    state.last_error = None
    state.consecutive_failures = 0

    return ExternalIngestionResult(
        client_id=client_id,
        events_ingested=events_ingested,
        requests_ingested=requests_ingested,
        alerts_created=alerts_created,
        workflows_started=workflows_started,
        procurement_requests_created=procurement_requests_created,
    )


async def _poll_client_with_session(
    db: AsyncSession,
    client_id: str,
) -> ExternalIngestionResult:
    client = await get_client(db, client_id)
    if client is None:
        raise ValueError(f"External client '{client_id}' not found")
    if client.connection_type != ConnectionType.REST:
        raise ValueError("Only REST polling is implemented for this client")

    async with RestConnector(base_url=client.api_endpoint) as connector:
        events_payload = await connector.get("/factory/events")
        requests_payload = await connector.get("/factory/requests")

    payload = ExternalIngestionPayloadIn(
        events=_extract_list(events_payload, ("events", "items", "data")),
        requests=_extract_list(requests_payload, ("requests", "items", "data")),
    )
    return await ingest_payload(db, client_id, payload)


async def poll_factory_simulator(db: AsyncSession, client_id: str) -> ExternalIngestionResult:
    return await _poll_client_with_session(db, client_id)


async def list_normalized_events(
    db: AsyncSession,
    client_id: Optional[str] = None,
    limit: int = 100,
) -> List[NormalizedEvent]:
    query = select(NormalizedEvent).order_by(NormalizedEvent.timestamp.desc()).limit(limit)
    if client_id:
        query = query.where(NormalizedEvent.client_id == client_id)
    result = await db.execute(query)
    return list(result.scalars().all())


async def list_normalized_requests(
    db: AsyncSession,
    client_id: Optional[str] = None,
    limit: int = 100,
) -> List[NormalizedRequest]:
    query = select(NormalizedRequest).order_by(NormalizedRequest.created_at.desc()).limit(limit)
    if client_id:
        query = query.where(NormalizedRequest.client_id == client_id)
    result = await db.execute(query)
    return list(result.scalars().all())


async def _mark_poll_error(
    db: AsyncSession,
    client_id: str,
    exc: Exception,
) -> None:
    client = await get_client(db, client_id)
    if client is None:
        return

    state = await _get_sync_state(db, client_id)
    client.status = ClientStatus.ERROR
    state.last_polled_at = _utcnow()
    state.last_error = str(exc)
    state.consecutive_failures += 1


def _is_due(state: ExternalClientSyncState, now: datetime) -> bool:
    if state.last_polled_at is None:
        return True
    next_poll_at = state.last_polled_at + timedelta(seconds=max(1, state.poll_interval_seconds))
    return next_poll_at <= now


class ExternalIngestionService:
    def __init__(self) -> None:
        self._task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()
        self._started_at: Optional[datetime] = None
        self._last_poll_at: Optional[datetime] = None
        self._successful_polls = 0
        self._failed_polls = 0
        self._total_events_ingested = 0
        self._total_requests_ingested = 0

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    async def start(self) -> None:
        if self.running:
            return
        self._stop_event = asyncio.Event()
        self._started_at = _utcnow()
        self._task = asyncio.create_task(self._polling_loop(), name="external-ingestion-loop")
        logger.info("External ingestion service started")

    async def stop(self) -> None:
        if self._task is None:
            return
        self._stop_event.set()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        finally:
            self._task = None
        logger.info("External ingestion service stopped")

    async def poll_now(self, client_id: Optional[str] = None) -> List[ExternalIngestionResult]:
        return await self._poll_due_clients(client_id=client_id, force=True)

    async def get_status(self) -> ExternalIngestionStatusOut:
        async with AsyncSessionLocal() as db:
            clients = await list_clients(db)
            states = await _get_sync_state_map(db, [client.id for client in clients])
            await db.commit()

        return ExternalIngestionStatusOut(
            running=self.running,
            started_at=self._started_at,
            last_poll_at=self._last_poll_at,
            active_clients=sum(1 for client in clients if client.status == ClientStatus.ACTIVE),
            successful_polls=self._successful_polls,
            failed_polls=self._failed_polls,
            total_events_ingested=self._total_events_ingested,
            total_requests_ingested=self._total_requests_ingested,
            clients=[_serialize_client(client, states.get(client.id)) for client in clients],
        )

    async def _polling_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                await self._poll_due_clients(force=False)
            except Exception:
                logger.exception("Unexpected error in external ingestion loop")

            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=1.0)
            except asyncio.TimeoutError:
                pass

    async def _poll_due_clients(
        self,
        client_id: Optional[str] = None,
        force: bool = False,
    ) -> List[ExternalIngestionResult]:
        results: List[ExternalIngestionResult] = []

        async with AsyncSessionLocal() as db:
            if client_id:
                client = await get_client(db, client_id)
                clients = [client] if client is not None else []
            else:
                clients = await list_clients(db, status=ClientStatus.ACTIVE)

            for client in clients:
                client_id_value = client.id
                state = await _get_sync_state(db, client_id_value)
                if not force and not _is_due(state, _utcnow()):
                    continue

                try:
                    result = await _poll_client_with_session(db, client_id_value)
                    await db.commit()
                    self._successful_polls += 1
                    self._total_events_ingested += result.events_ingested
                    self._total_requests_ingested += result.requests_ingested
                    results.append(result)
                except Exception as exc:
                    await db.rollback()
                    await _mark_poll_error(db, client_id_value, exc)
                    await db.commit()
                    self._failed_polls += 1
                    logger.warning("Polling failed for external client %s: %s", client_id_value, exc)

            self._last_poll_at = _utcnow()

        return results


_ingestion_service: Optional[ExternalIngestionService] = None


def get_external_ingestion_service() -> ExternalIngestionService:
    global _ingestion_service
    if _ingestion_service is None:
        _ingestion_service = ExternalIngestionService()
    return _ingestion_service
