"""
Test fixtures — async DB, test app client.
"""

from __future__ import annotations

import asyncio
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.core.database import Base, get_db
from backend.core.security import create_access_token, Role
from backend.main import create_app

# ── In-memory SQLite for tests ─────────────────────────────────────────────────
TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestSession = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session", autouse=True)
async def create_tables():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db() -> AsyncSession:
    async with TestSession() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client(db):
    app = create_app()

    async def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


def admin_token() -> str:
    return create_access_token("test-admin", extra={"role": Role.ADMIN, "email": "admin@test.com"})


def manager_token() -> str:
    return create_access_token("test-manager", extra={"role": Role.MANAGER, "email": "manager@test.com"})


def tech_token() -> str:
    return create_access_token("test-tech", extra={"role": Role.TECHNICIAN, "email": "tech@test.com"})


AUTH_ADMIN   = {"Authorization": f"Bearer {admin_token()}"}
AUTH_MANAGER = {"Authorization": f"Bearer {manager_token()}"}
AUTH_TECH    = {"Authorization": f"Bearer {tech_token()}"}
