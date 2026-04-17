"""
SQLAlchemy ORM models + Pydantic schemas for Users.
"""

from __future__ import annotations

import enum
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, EmailStr
from sqlalchemy import Boolean, DateTime, Enum, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.core.database import Base
from backend.core.security import Role


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


class User(Base):
    __tablename__ = "users"

    id:            Mapped[str]  = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    email:         Mapped[str]  = mapped_column(String(256), unique=True, nullable=False, index=True)
    full_name:     Mapped[str]  = mapped_column(String(256), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(256), nullable=False)
    role:          Mapped[str]  = mapped_column(String(32), default=Role.TECHNICIAN, nullable=False)
    company_id:    Mapped[Optional[str]] = mapped_column(String(64))
    is_active:     Mapped[bool] = mapped_column(Boolean, default=True)
    created_at:    Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    last_login:    Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


# ── Pydantic schemas ───────────────────────────────────────────────────────────
class UserCreate(BaseModel):
    email:      str
    full_name:  str
    password:   str
    role:       str = Role.TECHNICIAN
    company_id: Optional[str] = None


class UserUpdate(BaseModel):
    full_name:  Optional[str] = None
    role:       Optional[str] = None
    company_id: Optional[str] = None
    is_active:  Optional[bool] = None


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id:         str
    email:      str
    full_name:  str
    role:       str
    company_id: Optional[str]
    is_active:  bool
    created_at: datetime
    last_login: Optional[datetime]


class TokenOut(BaseModel):
    access_token:  str
    refresh_token: str
    token_type:    str = "bearer"
    expires_in:    int  # seconds
