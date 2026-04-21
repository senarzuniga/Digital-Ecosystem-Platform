"""
Tests for external source integration (Factory-Simulator style).
"""

from __future__ import annotations

import pytest

from backend.models.external_integration import ClientType, ExternalClientCreate, ExternalIngestionPayloadIn
from backend.services import alert_service, external_integration_service, procurement_service, workflow_service
from backend.tests.conftest import AUTH_ADMIN


@pytest.mark.asyncio
async def test_ensure_default_factory_client(db):
    client = await external_integration_service.ensure_default_factory_simulator_client(db)
    assert client.id == "digital_factory_1"
    assert client.type == ClientType.SIMULATED

    listed = await external_integration_service.list_clients(db)
    assert any(c.id == "digital_factory_1" for c in listed)


@pytest.mark.asyncio
async def test_ingest_payload_normalizes_and_integrates(db):
    await external_integration_service.create_client(
        db,
        ExternalClientCreate(
            id="ext_factory_test",
            name="External Factory Test",
            type=ClientType.SIMULATED,
            api_endpoint="http://localhost:9100",
        ),
    )

    payload = ExternalIngestionPayloadIn(
        events=[
            {
                "id": "event-001",
                "type": "temperature_spike",
                "machine_id": "MCH-001",
                "severity": "critical",
                "description": "Critical temperature detected",
                "timestamp": "2026-04-21T06:00:00Z",
            }
        ],
        requests=[
            {
                "id": "request-001",
                "request_type": "SPARE_PART",
                "machine_id": "MCH-001",
                "urgency": "high",
                "description": "Need replacement bearing",
            }
        ],
    )

    result = await external_integration_service.ingest_payload(db, "ext_factory_test", payload)
    assert result.events_ingested == 1
    assert result.requests_ingested == 1
    assert result.alerts_created == 1
    assert result.procurement_requests_created == 1
    assert result.workflows_started >= 2

    events = await external_integration_service.list_normalized_events(db, client_id="ext_factory_test")
    requests = await external_integration_service.list_normalized_requests(db, client_id="ext_factory_test")
    alerts = await alert_service.list_alerts(db, company_id="ext_factory_test")
    procurement_requests = await procurement_service.list_requests(db, company_id="ext_factory_test")
    workflows = await workflow_service.list_workflows(db, company_id="ext_factory_test")

    assert len(events) == 1
    assert len(requests) == 1
    assert len(alerts) >= 1
    assert len(procurement_requests) >= 1
    assert len(workflows) >= 2


@pytest.mark.asyncio
async def test_external_integration_api(client):
    create_res = await client.post(
        "/api/v1/external/clients",
        json={
            "id": "api_factory_client",
            "name": "API Factory Client",
            "type": "SIMULATED",
            "api_endpoint": "http://localhost:9100",
            "connection_type": "REST",
            "status": "active",
        },
        headers=AUTH_ADMIN,
    )
    assert create_res.status_code == 201

    ingest_res = await client.post(
        "/api/v1/external/ingest/api_factory_client",
        json={
            "events": [{"type": "vibration_alert", "severity": "high", "description": "Vibration above threshold"}],
            "requests": [{"request_type": "SERVICE", "urgency": "high", "description": "Service intervention required"}],
        },
        headers=AUTH_ADMIN,
    )
    assert ingest_res.status_code == 200
    body = ingest_res.json()
    assert body["events_ingested"] == 1
    assert body["requests_ingested"] == 1

    events_res = await client.get("/api/v1/external/events", params={"client_id": "api_factory_client"}, headers=AUTH_ADMIN)
    requests_res = await client.get("/api/v1/external/requests", params={"client_id": "api_factory_client"}, headers=AUTH_ADMIN)
    assert events_res.status_code == 200
    assert requests_res.status_code == 200
    assert len(events_res.json()) >= 1
    assert len(requests_res.json()) >= 1
