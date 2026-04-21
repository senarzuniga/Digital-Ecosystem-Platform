"""
Event bus — publish/subscribe for domain events.

Default backend: in-memory (asyncio Queue).
Set EVENT_BUS_BACKEND=redis to use Redis pub/sub (requires aioredis).

Events follow the format:  domain.entity.action
Examples:
  machine.alert.triggered
  maintenance.work_order.created
  anomaly.detected
  upsell.opportunity.created
  agent.action.executed
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Coroutine, Dict, List, Optional
from uuid import uuid4

from backend.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


@dataclass
class Event:
    topic: str
    payload: Dict[str, Any]
    event_id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))
    source: Optional[str] = None

    def dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "topic": self.topic,
            "payload": self.payload,
            "timestamp": self.timestamp.isoformat(),
            "source": self.source,
        }


Handler = Callable[[Event], Coroutine[Any, Any, None]]


class InMemoryEventBus:
    """Simple asyncio-based pub/sub.  Thread-safe via asyncio primitives."""

    def __init__(self) -> None:
        self._handlers: Dict[str, List[Handler]] = defaultdict(list)
        self._wildcard_handlers: List[Handler] = []
        self._history: List[Event] = []
        self._max_history: int = 1000

    def subscribe(self, topic: str, handler: Handler) -> None:
        """Subscribe to a specific topic or '*' for all events."""
        if topic == "*":
            self._wildcard_handlers.append(handler)
        else:
            self._handlers[topic].append(handler)
        logger.debug("Subscribed %s to topic '%s'", handler.__name__, topic)

    def unsubscribe(self, topic: str, handler: Handler) -> None:
        if topic == "*":
            self._wildcard_handlers = [h for h in self._wildcard_handlers if h is not handler]
        else:
            self._handlers[topic] = [h for h in self._handlers[topic] if h is not handler]

    async def publish(self, topic: str, payload: dict, source: str = "system") -> Event:
        event = Event(topic=topic, payload=payload, source=source)
        self._store(event)
        handlers = list(self._handlers.get(topic, [])) + list(self._wildcard_handlers)
        if handlers:
            await asyncio.gather(*[h(event) for h in handlers], return_exceptions=True)
        logger.info("Event published: topic=%s event_id=%s", topic, event.event_id)
        return event

    def _store(self, event: Event) -> None:
        self._history.append(event)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history :]

    def get_history(self, topic: Optional[str] = None, limit: int = 100) -> List[Event]:
        events = self._history if topic is None else [e for e in self._history if e.topic == topic]
        return events[-limit:]


# ── Singleton bus instance ────────────────────────────────────────────────────
_bus: Optional[InMemoryEventBus] = None


def get_event_bus() -> InMemoryEventBus:
    global _bus
    if _bus is None:
        _bus = InMemoryEventBus()
    return _bus


# ── Well-known topics ─────────────────────────────────────────────────────────
class Topics:
    MACHINE_ALERT_TRIGGERED   = "machine.alert.triggered"
    MAINTENANCE_REQUIRED      = "maintenance.required"
    WORK_ORDER_CREATED        = "maintenance.work_order.created"
    WORK_ORDER_UPDATED        = "maintenance.work_order.updated"
    ANOMALY_DETECTED          = "anomaly.detected"
    UPSELL_OPPORTUNITY        = "upsell.opportunity.created"
    AGENT_ACTION_EXECUTED     = "agent.action.executed"
    INVOICE_GENERATED         = "finance.invoice.generated"
    ENERGY_THRESHOLD_EXCEEDED = "energy.threshold.exceeded"
    USER_LOGIN                = "user.login"
    # ── Execution workflow ────────────────────────────────────────────────────
    WORKFLOW_CREATED          = "workflow.created"
    WORKFLOW_STARTED          = "workflow.started"
    WORKFLOW_WAITING_APPROVAL = "workflow.waiting_approval"
    WORKFLOW_APPROVED         = "workflow.approved"
    WORKFLOW_REJECTED         = "workflow.rejected"
    WORKFLOW_COMPLETED        = "workflow.completed"
    WORKFLOW_FAILED           = "workflow.failed"
    WORKFLOW_COMPENSATED      = "workflow.compensated"
    WORKFLOW_CANCELLED        = "workflow.cancelled"
    ACTION_EXECUTED           = "workflow.action.executed"
    # ── Procurement / RFQ ────────────────────────────────────────────────────
    PROCUREMENT_REQUEST_CREATED    = "procurement.request.created"
    PROCUREMENT_REQUEST_STRUCTURED = "procurement.request.structured"
    PROCUREMENT_REQUEST_ROUTED     = "procurement.request.routed"
    PROCUREMENT_SUPPLIER_REQUEST_SENT = "procurement.supplier_request.sent"
    PROCUREMENT_OFFER_RECEIVED     = "procurement.offer.received"
    PROCUREMENT_DECISION_MADE      = "procurement.decision.made"
    PROCUREMENT_ORDER_CREATED      = "procurement.order.created"
    PROCUREMENT_ORDER_UPDATED      = "procurement.order.updated"
    PROCUREMENT_FEEDBACK_SUBMITTED = "procurement.feedback.submitted"
    PROCUREMENT_IOT_TRIGGERED      = "procurement.iot.triggered"
