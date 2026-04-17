"""
Users router — CRUD, role management.
"""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from backend.core.security import Role, get_current_user_payload, require_roles
from backend.models.user import UserCreate, UserOut, UserUpdate
from backend.services import user_service

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/me", response_model=UserOut)
async def get_me(
    payload: dict = Depends(get_current_user_payload),
    db: AsyncSession = Depends(get_db),
):
    user = await user_service.get_user(db, payload["sub"])
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return UserOut.model_validate(user)


@router.get("/", response_model=List[UserOut])
async def list_users(
    company_id: Optional[str] = Query(None),
    role: Optional[str] = Query(None),
    _auth: dict = Depends(require_roles(Role.ADMIN, Role.MANAGER)),
    db: AsyncSession = Depends(get_db),
):
    users = await user_service.list_users(db, company_id=company_id, role=role)
    return [UserOut.model_validate(u) for u in users]


@router.post("/", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def create_user(
    data: UserCreate,
    _auth: dict = Depends(require_roles(Role.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    try:
        user = await user_service.create_user(db, data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return UserOut.model_validate(user)


@router.patch("/{user_id}", response_model=UserOut)
async def update_user(
    user_id: str,
    data: UserUpdate,
    _auth: dict = Depends(require_roles(Role.ADMIN, Role.MANAGER)),
    db: AsyncSession = Depends(get_db),
):
    user = await user_service.update_user(db, user_id, data)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return UserOut.model_validate(user)
