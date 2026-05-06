"""
External client registry + normalized external intake models.
"""

from __future__ import annotations

import enum
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.core.database import Base


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


class ClientType(str, enum.Enum):
    SIMULATED = "SIMULATED"
    REAL = "REAL"


class ConnectionType(str, enum.Enum):
    REST = "REST"
    WEBSOCKET = "WEBSOCKET"


class ClientStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"


class ExternalClient(Base):
    __tablename__ = "external_clients"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    company_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True, default="digital_factory_1")
    poll_interval_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    type: Mapped[ClientType] = mapped_column(Enum(ClientType), nullable=False)
    api_endpoint: Mapped[str] = mapped_column(String(512), nullable=False)
    connection_type: Mapped[ConnectionType] = mapped_column(Enum(ConnectionType), default=ConnectionType.REST)
    status: Mapped[ClientStatus] = mapped_column(Enum(ClientStatus), default=ClientStatus.ACTIVE, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)


class ExternalClientSyncState(Base):
    __tablename__ = "external_client_sync_state"

    client_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("external_clients.id", ondelete="CASCADE"),
        primary_key=True,
    )
    poll_interval_seconds: Mapped[int] = mapped_column(Integer, default=5)
    last_polled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[Optional[str]] = mapped_column(Text)
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)


class NormalizedEvent(Base):
    __tablename__ = "normalized_events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid4()))
    client_id: Mapped[str] = mapped_column(String(64), ForeignKey("external_clients.id", ondelete="CASCADE"), index=True)
    type: Mapped[str] = mapped_column(String(128), nullable=False)
    asset_id: Mapped[Optional[str]] = mapped_column(String(128))
    severity: Mapped[str] = mapped_column(String(32), default="info")
    description: Mapped[str] = mapped_column(Text, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)
    source_event_id: Mapped[Optional[str]] = mapped_column(String(128), index=True)
    raw_payload: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    def get_raw_payload(self) -> Dict[str, Any]:
        return json.loads(self.raw_payload) if self.raw_payload else {}


class NormalizedRequest(Base):
    __tablename__ = "normalized_requests"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid4()))
    client_id: Mapped[str] = mapped_column(String(64), ForeignKey("external_clients.id", ondelete="CASCADE"), index=True)
    type: Mapped[str] = mapped_column(String(128), nullable=False)
    structured_data: Mapped[str] = mapped_column(Text, nullable=False)
    urgency: Mapped[str] = mapped_column(String(32), default="medium")
    status: Mapped[str] = mapped_column(String(32), default="new")
    source_request_id: Mapped[Optional[str]] = mapped_column(String(128), index=True)
    procurement_request_id: Mapped[Optional[str]] = mapped_column(String(36), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)

    def get_structured_data(self) -> Dict[str, Any]:
        return json.loads(self.structured_data) if self.structured_data else {}


class ExternalClientCreate(BaseModel):
    id: str
    name: str
    company_id: str = "digital_factory_1"
    type: ClientType
    api_endpoint: str
    connection_type: ConnectionType = ConnectionType.REST
    status: ClientStatus = ClientStatus.ACTIVE
    poll_interval_seconds: int = 5


class ExternalClientUpdate(BaseModel):
    name: Optional[str] = None
    company_id: Optional[str] = None
    type: Optional[ClientType] = None
    api_endpoint: Optional[str] = None
    connection_type: Optional[ConnectionType] = None
    status: Optional[ClientStatus] = None
    poll_interval_seconds: Optional[int] = None


class ExternalClientOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    company_id: str
    type: ClientType
    api_endpoint: str
    connection_type: ConnectionType
    status: ClientStatus
    poll_interval_seconds: int = 5
    last_polled_at: Optional[datetime] = None
    last_seen_at: Optional[datetime] = None
    last_error: Optional[str] = None
    consecutive_failures: int = 0
    created_at: datetime
    updated_at: datetime


class ExternalIngestionPayloadIn(BaseModel):
    events: List[Dict[str, Any]] = Field(default_factory=list)
    requests: List[Dict[str, Any]] = Field(default_factory=list)


class ExternalIngestionResult(BaseModel):
    client_id: str
    events_ingested: int
    requests_ingested: int
    alerts_created: int
    workflows_started: int
    procurement_requests_created: int


class ExternalIngestionStatusOut(BaseModel):
    running: bool
    started_at: Optional[datetime]
    last_poll_at: Optional[datetime]
    active_clients: int
    successful_polls: int
    failed_polls: int
    total_events_ingested: int
    total_requests_ingested: int
    clients: List[ExternalClientOut] = Field(default_factory=list)


class NormalizedEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    client_id: str
    type: str
    asset_id: Optional[str]
    severity: str
    description: str
    timestamp: datetime
    source_event_id: Optional[str]
    created_at: datetime


class NormalizedRequestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    client_id: str
    type: str
    structured_data: str
    urgency: str
    status: str
    source_request_id: Optional[str]
    procurement_request_id: Optional[str]
    created_at: datetime
