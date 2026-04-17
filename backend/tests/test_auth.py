"""
Tests for Auth and User management.
"""

import pytest

from backend.core.security import Role, create_access_token, decode_token, hash_password, verify_password
from backend.models.user import UserCreate, UserUpdate
from backend.services import user_service
from backend.tests.conftest import AUTH_ADMIN, AUTH_TECH


# ── Security unit tests ────────────────────────────────────────────────────────
def test_password_hashing():
    hashed = hash_password("MySecret123!")
    assert verify_password("MySecret123!", hashed)
    assert not verify_password("WrongPassword", hashed)


def test_token_roundtrip():
    token = create_access_token("user-001", extra={"role": Role.ADMIN})
    payload = decode_token(token)
    assert payload["sub"] == "user-001"
    assert payload["role"] == Role.ADMIN


def test_expired_token_raises():
    from jose import jwt
    from backend.core.config import get_settings
    from datetime import datetime, timezone, timedelta
    settings = get_settings()
    payload = {"sub": "user-001", "exp": datetime.now(tz=timezone.utc) - timedelta(seconds=10)}
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        decode_token(token)
    assert exc_info.value.status_code == 401


# ── User service tests ─────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_create_user(db):
    user = await user_service.create_user(db, UserCreate(
        email="test@example.com",
        full_name="Test User",
        password="Password123!",
        role=Role.TECHNICIAN,
    ))
    assert user.id is not None
    assert user.email == "test@example.com"
    assert user.hashed_password != "Password123!"


@pytest.mark.asyncio
async def test_duplicate_email_raises(db):
    data = UserCreate(email="dup@example.com", full_name="Dup User", password="Pass1!")
    await user_service.create_user(db, data)
    with pytest.raises(ValueError, match="already registered"):
        await user_service.create_user(db, data)


@pytest.mark.asyncio
async def test_authenticate_user_success(db):
    await user_service.create_user(db, UserCreate(
        email="auth@example.com",
        full_name="Auth User",
        password="Correct1!",
        role=Role.MANAGER,
    ))
    user = await user_service.authenticate_user(db, "auth@example.com", "Correct1!")
    assert user is not None
    assert user.last_login is not None


@pytest.mark.asyncio
async def test_authenticate_user_wrong_password(db):
    await user_service.create_user(db, UserCreate(
        email="wrong@example.com",
        full_name="Wrong User",
        password="Correct1!",
    ))
    result = await user_service.authenticate_user(db, "wrong@example.com", "WrongPass")
    assert result is None


# ── API tests ──────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_api_register_and_login(client):
    reg = await client.post("/api/v1/auth/register", json={
        "email": "newuser@dep.com",
        "full_name": "New User",
        "password": "NewPass123!",
    })
    assert reg.status_code == 201

    login = await client.post("/api/v1/auth/login", data={
        "username": "newuser@dep.com",
        "password": "NewPass123!",
    })
    assert login.status_code == 200
    assert "access_token" in login.json()


@pytest.mark.asyncio
async def test_api_me_requires_auth(client):
    resp = await client.get("/api/v1/users/me")
    assert resp.status_code in (401, 403)  # HTTPBearer returns 403 without header, 401 with invalid token


@pytest.mark.asyncio
async def test_api_list_users_requires_manager(client):
    resp = await client.get("/api/v1/users/", headers=AUTH_TECH)
    assert resp.status_code == 403

    resp2 = await client.get("/api/v1/users/", headers=AUTH_ADMIN)
    assert resp2.status_code == 200
