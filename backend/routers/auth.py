"""
Auth router — login, refresh token.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import get_settings
from backend.core.database import get_db
from backend.core.events import Topics, get_event_bus
from backend.core.security import create_access_token, create_refresh_token, decode_token
from backend.models.user import TokenOut, UserCreate, UserOut
from backend.services.user_service import authenticate_user, create_user

router = APIRouter(prefix="/auth", tags=["Authentication"])
settings = get_settings()


@router.post("/login", response_model=TokenOut)
async def login(
    form: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    user = await authenticate_user(db, form.username, form.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token  = create_access_token(user.id, extra={"role": user.role, "email": user.email})
    refresh_token = create_refresh_token(user.id)

    bus = get_event_bus()
    await bus.publish(Topics.USER_LOGIN, {"user_id": user.id, "email": user.email}, source="auth")

    return TokenOut(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/refresh", response_model=TokenOut)
async def refresh(token: str):
    payload = decode_token(token)
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=400, detail="Invalid token type")
    user_id = payload["sub"]
    access  = create_access_token(user_id)
    refresh = create_refresh_token(user_id)
    return TokenOut(
        access_token=access,
        refresh_token=refresh,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(data: UserCreate, db: AsyncSession = Depends(get_db)):
    """Self-registration (creates TECHNICIAN role by default)."""
    try:
        user = await create_user(db, data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return UserOut.model_validate(user)
