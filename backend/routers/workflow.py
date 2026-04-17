"""
Execution Workflow Router
=========================
Exposes the detect → decide → act → verify engine via REST.

Routes
------
POST   /workflows                      Create (idempotent)
POST   /workflows/{id}/execute         Start / resume execution
POST   /workflows/{id}/approve         Approve (manager/admin only)
POST   /workflows/{id}/reject          Reject  (manager/admin only)
POST   /workflows/{id}/cancel          Cancel
GET    /workflows/{id}                 Get workflow detail
GET    /workflows                      List (filterable by company, state, trigger)
GET    /workflows/{id}/audit           List ActionAudit records for the workflow
"""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from backend.core.security import Role, get_current_user_payload, require_roles
from backend.models.workflow import (
    ActionAuditOut,
    RejectIn,
    WorkflowCreate,
    WorkflowOut,
    WorkflowState,
    WorkflowTriggerType,
)
from backend.services import workflow_service

router = APIRouter(prefix="/workflows", tags=["Execution Workflows"])


@router.post("/", response_model=WorkflowOut, status_code=status.HTTP_201_CREATED)
async def create_workflow(
    data: WorkflowCreate,
    payload: dict = Depends(get_current_user_payload),
    db: AsyncSession = Depends(get_db),
):
    """Create a new workflow (idempotent: same idempotency_key returns the existing record)."""
    wf = await workflow_service.create_workflow(db, data, created_by=payload.get("sub"))
    return WorkflowOut.model_validate(wf)


@router.post("/{workflow_id}/execute", response_model=WorkflowOut)
async def execute_workflow(
    workflow_id: str,
    payload: dict = Depends(require_roles(Role.ADMIN, Role.MANAGER)),
    db: AsyncSession = Depends(get_db),
):
    """
    Start (or resume) workflow execution.
    If the workflow requires approval, it pauses at WAITING_APPROVAL.
    """
    try:
        wf = await workflow_service.execute_workflow(db, workflow_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return WorkflowOut.model_validate(wf)


@router.post("/{workflow_id}/approve", response_model=WorkflowOut)
async def approve_workflow(
    workflow_id: str,
    payload: dict = Depends(require_roles(Role.ADMIN, Role.MANAGER)),
    db: AsyncSession = Depends(get_db),
):
    """Approve a workflow that is WAITING_APPROVAL, then continue execution."""
    try:
        wf = await workflow_service.approve_workflow(
            db, workflow_id, approved_by=payload.get("sub", "")
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return WorkflowOut.model_validate(wf)


@router.post("/{workflow_id}/reject", response_model=WorkflowOut)
async def reject_workflow(
    workflow_id: str,
    data: RejectIn,
    payload: dict = Depends(require_roles(Role.ADMIN, Role.MANAGER)),
    db: AsyncSession = Depends(get_db),
):
    """Reject a workflow that is WAITING_APPROVAL."""
    try:
        wf = await workflow_service.reject_workflow(
            db, workflow_id, user_id=payload.get("sub", ""), reason=data.reason
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return WorkflowOut.model_validate(wf)


@router.post("/{workflow_id}/cancel", response_model=WorkflowOut)
async def cancel_workflow(
    workflow_id: str,
    _auth: dict = Depends(require_roles(Role.ADMIN, Role.MANAGER)),
    db: AsyncSession = Depends(get_db),
):
    """Cancel a pending or running workflow."""
    try:
        wf = await workflow_service.cancel_workflow(db, workflow_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return WorkflowOut.model_validate(wf)


@router.get("/{workflow_id}", response_model=WorkflowOut)
async def get_workflow(
    workflow_id: str,
    _auth: dict = Depends(get_current_user_payload),
    db: AsyncSession = Depends(get_db),
):
    """Get a single workflow by ID."""
    wf = await workflow_service.get_workflow(db, workflow_id)
    if wf is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found")
    return WorkflowOut.model_validate(wf)


@router.get("/", response_model=List[WorkflowOut])
async def list_workflows(
    company_id:   Optional[str]                  = Query(None),
    state:        Optional[WorkflowState]        = Query(None),
    trigger_type: Optional[WorkflowTriggerType]  = Query(None),
    limit:  int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    _auth: dict = Depends(get_current_user_payload),
    db: AsyncSession = Depends(get_db),
):
    """List workflows with optional filters."""
    workflows = await workflow_service.list_workflows(
        db,
        company_id=company_id,
        state=state,
        trigger_type=trigger_type,
        limit=limit,
        offset=offset,
    )
    return [WorkflowOut.model_validate(w) for w in workflows]


@router.get("/{workflow_id}/audit", response_model=List[ActionAuditOut])
async def get_workflow_audit(
    workflow_id: str,
    _auth: dict = Depends(get_current_user_payload),
    db: AsyncSession = Depends(get_db),
):
    """Return all ActionAudit records for a workflow (full execution trail)."""
    # Verify workflow exists
    wf = await workflow_service.get_workflow(db, workflow_id)
    if wf is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found")
    audits = await workflow_service.list_action_audits(db, workflow_id=workflow_id)
    return [ActionAuditOut.model_validate(a) for a in audits]
