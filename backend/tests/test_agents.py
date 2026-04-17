"""
Tests for AI Agent Orchestration service.
"""

import pytest

from backend.services.agent_service import (
    AgentMemory,
    MaintenanceAgent,
    OptimizationAgent,
    CommercialAgent,
    get_orchestrator,
    get_action_log,
)
from backend.core.events import Event, Topics


@pytest.mark.asyncio
async def test_agent_memory():
    mem = AgentMemory(agent_id="test")
    mem.remember("key1", "value1")
    mem.remember("key1", "value2")  # overwrite with newer entry
    assert mem.recall("key1") == "value2"
    assert mem.recall("nonexistent") is None


@pytest.mark.asyncio
async def test_maintenance_agent_creates_wo_on_alert(db):
    agent = MaintenanceAgent()
    event = Event(
        topic=Topics.MACHINE_ALERT_TRIGGERED,
        payload={
            "alert_id":   "alert-001",
            "company_id": "ACME",
            "asset_id":   "machine-001",
            "severity":   "critical",
            "title":      "Critical vibration",
        },
    )
    result = await agent.handle_event(event, db)
    assert result is not None
    assert "work_order_id" in result


@pytest.mark.asyncio
async def test_maintenance_agent_deduplication(db):
    agent = MaintenanceAgent()
    asset_id = "machine-dedup"
    event = Event(
        topic=Topics.MACHINE_ALERT_TRIGGERED,
        payload={
            "alert_id":   "alert-dedup",
            "company_id": "ACME",
            "asset_id":   asset_id,
            "severity":   "high",
            "title":      "High vibration",
        },
    )
    # First call should create WO
    result1 = await agent.handle_event(event, db)
    assert "work_order_id" in result1

    # Second call with same asset should be skipped
    result2 = await agent.handle_event(event, db)
    assert result2.get("skipped") is True


@pytest.mark.asyncio
async def test_optimization_agent_energy_recommendation(db):
    agent = OptimizationAgent()
    event = Event(
        topic=Topics.ENERGY_THRESHOLD_EXCEEDED,
        payload={
            "company_id":  "ACME",
            "asset_id":    "machine-001",
            "current_kwh": 65.0,
            "target_kwh":  50.0,
        },
    )
    result = await agent.handle_event(event, db)
    assert result is not None
    assert "recommendation" in result
    assert result["potential_saving_pct"] > 0


@pytest.mark.asyncio
async def test_orchestrator_routes_event(db):
    orch = get_orchestrator()
    event = Event(
        topic=Topics.MACHINE_ALERT_TRIGGERED,
        payload={
            "alert_id":   "orch-alert-001",
            "company_id": "ACME",
            "asset_id":   "machine-orch",
            "severity":   "warning",
            "title":      "Orchestrator test",
        },
    )
    results = await orch.route(event, db)
    # MaintenanceAgent and CommercialAgent should both respond
    agent_ids = [r["agent_id"] for r in results]
    assert "maintenance_agent" in agent_ids


@pytest.mark.asyncio
async def test_action_log_populated(db):
    agent = MaintenanceAgent()
    event = Event(
        topic=Topics.MACHINE_ALERT_TRIGGERED,
        payload={
            "alert_id":   "log-test-alert",
            "company_id": "ACME",
            "asset_id":   "machine-log",
            "severity":   "high",
            "title":      "Log test",
        },
    )
    await agent.handle_event(event, db)
    log = get_action_log(limit=50)
    assert len(log) > 0
    assert any(r.agent_id == "maintenance_agent" for r in log)
