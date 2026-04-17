"""
Database engine, session factory, and base model.
Uses SQLAlchemy 2.x async API.
Development default: SQLite (aiosqlite).
Production: swap DATABASE_URL to postgresql+asyncpg://...
"""

from __future__ import annotations

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from backend.core.config import get_settings

settings = get_settings()

# ── Engine ─────────────────────────────────────────────────────────────────────
_engine_kwargs: dict = {"echo": settings.DEBUG}

if settings.DATABASE_URL.startswith("sqlite"):
    _engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_async_engine(settings.DATABASE_URL, **_engine_kwargs)

# ── Session factory ────────────────────────────────────────────────────────────
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


# ── Declarative base ───────────────────────────────────────────────────────────
class Base(DeclarativeBase):
    pass


# ── Dependency injector ────────────────────────────────────────────────────────
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ── Schema creation helper ────────────────────────────────────────────────────
async def create_all_tables() -> None:
    """Create all tables. Called at application startup."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
