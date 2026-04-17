"""
SQLAlchemy ORM models + Pydantic schemas for the Execution Workflow Engine.

ExecutionWorkflow
  Tracks the full detect → decide → act → verify operational loop.
  Supports idempotency, human-approval gates, retry tracking, and compensation.

ActionAudit
  Immutable per-action audit record.  One row per execution attempt.
  Provides a full, tamper-evident audit trail of every operation.
"""

from __future__ import annotations

import enum
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, ConfigDict
from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.core.database import Base


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


# ── Enums ──────────────────────────────────────────────────────────────────────

class WorkflowTriggerType(str, enum.Enum):
    ALERT    = "alert"
    SCHEDULE = "schedule"
    MANUAL   = "manual"
    AGENT    = "agent"


class WorkflowState(str, enum.Enum):
    PENDING          = "pending"
    RUNNING          = "running"
    WAITING_APPROVAL = "waiting_approval"
    APPROVED         = "approved"
    REJECTED         = "rejected"
    COMPLETED        = "completed"
    FAILED           = "failed"
    COMPENSATING     = "compensating"
    COMPENSATED      = "compensated"
    CANCELLED        = "cancelled"


class WorkflowPhase(str, enum.Enum):
    DETECT = "detect"
    DECIDE = "decide"
    ACT    = "act"
    VERIFY = "verify"


class ActionStatus(str, enum.Enum):
    PENDING     = "pending"
    EXECUTING   = "executing"
    SUCCESS     = "success"
    FAILED      = "failed"
    COMPENSATED = "compensated"
    SKIPPED     = "skipped"


# ── ORM: ExecutionWorkflow ────────────────────────────────────────────────────

class ExecutionWorkflow(Base):
    """
    Represents one end-to-end operational cycle:
        DETECT (what is happening?) →
        DECIDE (what should we do?) →
        ACT    (execute the actions) →
        VERIFY (did it work?)

    State machine:
        PENDING → RUNNING → WAITING_APPROVAL ─► REJECTED
                                     │
                                     ▼ (approved / not required)
                           RUNNING → COMPLETED
                                   └─► FAILED → COMPENSATING → COMPENSATED
        PENDING|RUNNING → CANCELLED
    """

    __tablename__ = "execution_workflows"

    id:              Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    idempotency_key: Mapped[str] = mapped_column(
        String(128), unique=True, nullable=False, index=True
    )
    company_id:      Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    asset_id:        Mapped[Optional[str]] = mapped_column(String(36))
    trigger_type:    Mapped[WorkflowTriggerType] = mapped_column(
        Enum(WorkflowTriggerType), default=WorkflowTriggerType.MANUAL
    )
    trigger_id:      Mapped[Optional[str]] = mapped_column(String(36))  # alert/agent id
    title:           Mapped[str] = mapped_column(String(256), nullable=False)
    description:     Mapped[Optional[str]] = mapped_column(Text)

    # ── State machine ─────────────────────────────────────────────────────────
    state:           Mapped[WorkflowState] = mapped_column(
        Enum(WorkflowState), default=WorkflowState.PENDING, index=True
    )
    current_phase:   Mapped[Optional[WorkflowPhase]] = mapped_column(Enum(WorkflowPhase))

    # ── Approval gate ─────────────────────────────────────────────────────────
    requires_approval: Mapped[bool] = mapped_column(Boolean, default=False)
    approved_by:       Mapped[Optional[str]] = mapped_column(String(36))
    approved_at:       Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    rejection_reason:  Mapped[Optional[str]] = mapped_column(Text)

    # ── Phase data (JSON text; swap to JSONB in PostgreSQL) ───────────────────
    detect_data:         Mapped[Optional[str]] = mapped_column(Text)
    decision_data:       Mapped[Optional[str]] = mapped_column(Text)
    actions_planned:     Mapped[Optional[str]] = mapped_column(Text)
    actions_executed:    Mapped[Optional[str]] = mapped_column(Text)
    verification_result: Mapped[Optional[str]] = mapped_column(Text)

    # ── Retry / error ─────────────────────────────────────────────────────────
    retry_count:   Mapped[int] = mapped_column(Integer, default=0)
    max_retries:   Mapped[int] = mapped_column(Integer, default=3)
    error_message: Mapped[Optional[str]] = mapped_column(Text)

    # ── Audit metadata ────────────────────────────────────────────────────────
    created_by:   Mapped[Optional[str]] = mapped_column(String(36))
    created_at:   Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    started_at:   Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    action_audits: Mapped[List["ActionAudit"]] = relationship(
        "ActionAudit",
        back_populates="workflow",
        foreign_keys="[ActionAudit.workflow_id]",
        lazy="select",
    )

    # ── JSON helpers ──────────────────────────────────────────────────────────
    def get_detect_data(self) -> Dict[str, Any]:
        return json.loads(self.detect_data) if self.detect_data else {}

    def set_detect_data(self, data: Dict[str, Any]) -> None:
        self.detect_data = json.dumps(data)

    def get_decision_data(self) -> Dict[str, Any]:
        return json.loads(self.decision_data) if self.decision_data else {}

    def set_decision_data(self, data: Dict[str, Any]) -> None:
        self.decision_data = json.dumps(data)

    def get_actions_planned(self) -> List[Dict[str, Any]]:
        return json.loads(self.actions_planned) if self.actions_planned else []

    def set_actions_planned(self, data: List[Dict[str, Any]]) -> None:
        self.actions_planned = json.dumps(data)

    def get_actions_executed(self) -> List[Dict[str, Any]]:
        return json.loads(self.actions_executed) if self.actions_executed else []

    def set_actions_executed(self, data: List[Dict[str, Any]]) -> None:
        self.actions_executed = json.dumps(data)

    def get_verification_result(self) -> Dict[str, Any]:
        return json.loads(self.verification_result) if self.verification_result else {}

    def set_verification_result(self, data: Dict[str, Any]) -> None:
        self.verification_result = json.dumps(data)


# ── ORM: ActionAudit ─────────────────────────────────────────────────────────

class ActionAudit(Base):
    """
    Immutable per-action audit record.  Written once, never updated.
    A new row is created for every execution attempt (retry).

    Provides the full audit trail: who, what, when, input, output, duration.
    """

    __tablename__ = "action_audits"

    id:             Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    workflow_id:    Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("execution_workflows.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    company_id:     Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    asset_id:       Mapped[Optional[str]] = mapped_column(String(36))

    # ── Actor ─────────────────────────────────────────────────────────────────
    actor_type:     Mapped[str] = mapped_column(String(32), default="system")  # agent|user|system
    actor_id:       Mapped[Optional[str]] = mapped_column(String(36))

    # ── Action ────────────────────────────────────────────────────────────────
    action_type:    Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    target_type:    Mapped[Optional[str]] = mapped_column(String(32))
    target_id:      Mapped[Optional[str]] = mapped_column(String(36))

    # ── Payloads (JSON text) ──────────────────────────────────────────────────
    input_payload:  Mapped[Optional[str]] = mapped_column(Text)
    output_payload: Mapped[Optional[str]] = mapped_column(Text)

    # ── Execution bookkeeping ─────────────────────────────────────────────────
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(128), index=True)
    status:          Mapped[ActionStatus] = mapped_column(
        Enum(ActionStatus), default=ActionStatus.PENDING, index=True
    )
    attempt_number:  Mapped[int] = mapped_column(Integer, default=1)
    error_message:   Mapped[Optional[str]] = mapped_column(Text)
    duration_ms:     Mapped[Optional[int]] = mapped_column(Integer)
    executed_at:     Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    workflow: Mapped[Optional["ExecutionWorkflow"]] = relationship(
        "ExecutionWorkflow",
        back_populates="action_audits",
        foreign_keys=[workflow_id],
        lazy="select",
    )

    def get_input_payload(self) -> Dict[str, Any]:
        return json.loads(self.input_payload) if self.input_payload else {}

    def get_output_payload(self) -> Dict[str, Any]:
        return json.loads(self.output_payload) if self.output_payload else {}


# ── Pydantic schemas ───────────────────────────────────────────────────────────

class WorkflowCreate(BaseModel):
    idempotency_key:  str
    company_id:       str
    asset_id:         Optional[str] = None
    trigger_type:     WorkflowTriggerType = WorkflowTriggerType.MANUAL
    trigger_id:       Optional[str] = None
    title:            str
    description:      Optional[str] = None
    requires_approval: bool = False
    max_retries:      int = 3


class RejectIn(BaseModel):
    reason: str


class ActionAuditOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id:              str
    workflow_id:     Optional[str]
    company_id:      str
    asset_id:        Optional[str]
    actor_type:      str
    actor_id:        Optional[str]
    action_type:     str
    target_type:     Optional[str]
    target_id:       Optional[str]
    idempotency_key: Optional[str]
    status:          ActionStatus
    attempt_number:  int
    error_message:   Optional[str]
    duration_ms:     Optional[int]
    executed_at:     datetime


class WorkflowOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id:               str
    idempotency_key:  str
    company_id:       str
    asset_id:         Optional[str]
    trigger_type:     WorkflowTriggerType
    trigger_id:       Optional[str]
    title:            str
    description:      Optional[str]
    state:            WorkflowState
    current_phase:    Optional[WorkflowPhase]
    requires_approval: bool
    approved_by:      Optional[str]
    approved_at:      Optional[datetime]
    rejection_reason: Optional[str]
    retry_count:      int
    max_retries:      int
    error_message:    Optional[str]
    created_by:       Optional[str]
    created_at:       datetime
    started_at:       Optional[datetime]
    completed_at:     Optional[datetime]
    # Decoded JSON fields
    detect_data:         Optional[str]
    decision_data:       Optional[str]
    actions_planned:     Optional[str]
    actions_executed:    Optional[str]
    verification_result: Optional[str]
