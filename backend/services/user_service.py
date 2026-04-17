"""
User / Auth Service — creation, lookup, password validation.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.security import hash_password, verify_password
from backend.models.user import User, UserCreate, UserUpdate

logger = logging.getLogger(__name__)


async def create_user(db: AsyncSession, data: UserCreate) -> User:
    existing = await get_user_by_email(db, data.email)
    if existing:
        raise ValueError(f"Email '{data.email}' already registered")
    user = User(
        email=data.email.lower().strip(),
        full_name=data.full_name,
        hashed_password=hash_password(data.password),
        role=data.role,
        company_id=data.company_id,
    )
    db.add(user)
    await db.flush()
    logger.info("Created user %s (role=%s)", user.email, user.role)
    return user


async def get_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
    result = await db.execute(select(User).where(User.email == email.lower().strip()))
    return result.scalar_one_or_none()


async def get_user(db: AsyncSession, user_id: str) -> Optional[User]:
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def authenticate_user(db: AsyncSession, email: str, password: str) -> Optional[User]:
    user = await get_user_by_email(db, email)
    if user is None or not user.is_active:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    user.last_login = datetime.now(tz=timezone.utc)
    await db.flush()
    return user


async def list_users(
    db: AsyncSession,
    company_id: Optional[str] = None,
    role: Optional[str] = None,
    limit: int = 100,
) -> List[User]:
    q = select(User)
    if company_id:
        q = q.where(User.company_id == company_id)
    if role:
        q = q.where(User.role == role)
    q = q.order_by(User.created_at.desc()).limit(limit)
    result = await db.execute(q)
    return list(result.scalars().all())


async def update_user(db: AsyncSession, user_id: str, data: UserUpdate) -> Optional[User]:
    user = await get_user(db, user_id)
    if user is None:
        return None
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(user, key, value)
    await db.flush()
    return user


async def ensure_default_admin(db: AsyncSession) -> None:
    """Create a default admin user if none exists (first-run bootstrap)."""
    from backend.core.security import Role
    from backend.models.user import UserCreate
    result = await db.execute(select(User).where(User.role == Role.ADMIN).limit(1))
    if result.scalar_one_or_none() is None:
        await create_user(db, UserCreate(
            email="admin@dep.local",
            full_name="Platform Administrator",
            password="Admin1234!",
            role=Role.ADMIN,
        ))
        logger.warning("Default admin created: admin@dep.local / Admin1234! — CHANGE THIS PASSWORD.")
