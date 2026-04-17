"""
Agents router.
"""

from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from backend.core.events import get_event_bus
from backend.core.security import Role, get_current_user_payload, require_roles
from backend.services.agent_service import get_action_log, get_orchestrator, run_agent_action

router = APIRouter(prefix="/agents", tags=["AI Agents"])


@router.get("/")
async def list_agents(_auth: dict = Depends(get_current_user_payload)):
    return get_orchestrator().list_agents()


class ActionRequest(BaseModel):
    action:  str
    payload: Dict[str, Any] = {}


@router.post("/{agent_id}/run")
async def run_action(
    agent_id: str,
    req: ActionRequest,
    _auth: dict = Depends(require_roles(Role.ADMIN, Role.MANAGER)),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await run_agent_action(db, agent_id, req.action, req.payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return result


@router.get("/log")
async def action_log(
    limit: int = 100,
    _auth: dict = Depends(get_current_user_payload),
):
    records = get_action_log(limit=limit)
    return [
        {
            "action_id":    r.action_id,
            "agent_id":     r.agent_id,
            "action":       r.action,
            "success":      r.success,
            "error":        r.error,
            "executed_at":  r.executed_at.isoformat(),
        }
        for r in records
    ]


@router.get("/events/history")
async def event_history(
    topic: str | None = None,
    limit: int = 100,
    _auth: dict = Depends(get_current_user_payload),
):
    bus = get_event_bus()
    events = bus.get_history(topic=topic, limit=limit)
    return [e.dict() for e in events]
