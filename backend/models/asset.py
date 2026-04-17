"""
SQLAlchemy ORM models + Pydantic schemas for Assets and Machines.
"""

from __future__ import annotations

import enum
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, field_validator
from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.core.database import Base


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


# ── Enums ──────────────────────────────────────────────────────────────────────
class AssetStatus(str, enum.Enum):
    ONLINE  = "online"
    WARNING = "warning"
    OFFLINE = "offline"
    MAINTENANCE = "maintenance"


class ConnectorType(str, enum.Enum):
    MQTT   = "mqtt"
    OPCUA  = "opcua"
    REST   = "rest"
    MANUAL = "manual"


# ── ORM Model ─────────────────────────────────────────────────────────────────
class Asset(Base):
    __tablename__ = "assets"

    id:           Mapped[str]   = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    company_id:   Mapped[str]   = mapped_column(String(64), index=True, nullable=False)
    name:         Mapped[str]   = mapped_column(String(256), nullable=False)
    asset_type:   Mapped[str]   = mapped_column(String(128), nullable=False)
    serial_number: Mapped[Optional[str]] = mapped_column(String(128))
    manufacturer: Mapped[Optional[str]] = mapped_column(String(128))
    model_number: Mapped[Optional[str]] = mapped_column(String(128))
    location:     Mapped[Optional[str]] = mapped_column(String(256))
    install_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    status:       Mapped[AssetStatus] = mapped_column(
        Enum(AssetStatus), default=AssetStatus.ONLINE, nullable=False
    )
    connector_type: Mapped[ConnectorType] = mapped_column(
        Enum(ConnectorType), default=ConnectorType.MANUAL
    )
    connector_config: Mapped[Optional[str]] = mapped_column(Text)  # JSON string
    oee:           Mapped[Optional[float]] = mapped_column(Float)
    health_score:  Mapped[Optional[float]] = mapped_column(Float)
    age_years:     Mapped[Optional[float]] = mapped_column(Float)
    is_active:     Mapped[bool]  = mapped_column(Boolean, default=True)
    created_at:    Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at:    Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    # Relationships
    telemetry:    Mapped[list["MachineTelemetry"]] = relationship("MachineTelemetry", back_populates="asset", lazy="select")
    work_orders:  Mapped[list["WorkOrder"]]        = relationship("WorkOrder",        back_populates="asset", lazy="select")
    alerts:       Mapped[list["Alert"]]            = relationship("Alert",            back_populates="asset", lazy="select")
    energy_readings: Mapped[list["EnergyReading"]] = relationship("EnergyReading",   back_populates="asset", lazy="select")


class MachineTelemetry(Base):
    """Time-series telemetry record per asset. Swappable with InfluxDB/Timescale."""
    __tablename__ = "machine_telemetry"

    id:          Mapped[int]    = mapped_column(Integer, primary_key=True, autoincrement=True)
    asset_id:    Mapped[str]    = mapped_column(String(36), ForeignKey("assets.id", ondelete="CASCADE"), index=True)
    timestamp:   Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)
    temperature: Mapped[Optional[float]] = mapped_column(Float)
    vibration:   Mapped[Optional[float]] = mapped_column(Float)
    power_kw:    Mapped[Optional[float]] = mapped_column(Float)
    pressure:    Mapped[Optional[float]] = mapped_column(Float)
    speed_rpm:   Mapped[Optional[float]] = mapped_column(Float)
    oee:         Mapped[Optional[float]] = mapped_column(Float)

    asset: Mapped["Asset"] = relationship("Asset", back_populates="telemetry")


# ── Pydantic schemas ───────────────────────────────────────────────────────────
class AssetCreate(BaseModel):
    company_id:      str
    name:            str
    asset_type:      str
    serial_number:   Optional[str] = None
    manufacturer:    Optional[str] = None
    model_number:    Optional[str] = None
    location:        Optional[str] = None
    install_date:    Optional[datetime] = None
    connector_type:  ConnectorType = ConnectorType.MANUAL
    connector_config: Optional[str] = None


class AssetUpdate(BaseModel):
    name:            Optional[str] = None
    status:          Optional[AssetStatus] = None
    location:        Optional[str] = None
    oee:             Optional[float] = None
    health_score:    Optional[float] = None
    is_active:       Optional[bool] = None


class AssetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id:            str
    company_id:    str
    name:          str
    asset_type:    str
    serial_number: Optional[str]
    manufacturer:  Optional[str]
    location:      Optional[str]
    install_date:  Optional[datetime]
    status:        AssetStatus
    connector_type: ConnectorType
    oee:           Optional[float]
    health_score:  Optional[float]
    age_years:     Optional[float]
    is_active:     bool
    created_at:    datetime
    updated_at:    datetime


class TelemetryCreate(BaseModel):
    asset_id:    str
    temperature: Optional[float] = None
    vibration:   Optional[float] = None
    power_kw:    Optional[float] = None
    pressure:    Optional[float] = None
    speed_rpm:   Optional[float] = None
    oee:         Optional[float] = None


class TelemetryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id:          int
    asset_id:    str
    timestamp:   datetime
    temperature: Optional[float]
    vibration:   Optional[float]
    power_kw:    Optional[float]
    pressure:    Optional[float]
    speed_rpm:   Optional[float]
    oee:         Optional[float]
