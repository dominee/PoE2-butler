"""API key management endpoints — create, inspect, and revoke per-user machine keys.

These routes are SPA-only (session + CSRF required).  The Discord bot uses the key
obtained here via ``Authorization: Bearer hob_…`` on the data endpoints.

Only one non-revoked key is allowed per user.  Creating a new key when one already
exists automatically revokes the previous one.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.db.base import get_session
from app.db.models import User, UserApiKey
from app.deps import get_current_user, require_csrf
from app.security.api_keys import generate_api_key

router = APIRouter(prefix="/api/me/api-key", tags=["api-keys", "bot-api"])


class ApiKeyStatus(BaseModel):
    """Current key metadata — the secret is never returned after creation."""

    id: uuid.UUID
    prefix: str
    name: str | None
    created_at: datetime
    last_used_at: datetime | None


class ApiKeyCreated(BaseModel):
    """Returned once on creation.  ``full_key`` is never stored and cannot be recovered."""

    id: uuid.UUID
    prefix: str
    name: str | None
    created_at: datetime
    full_key: str


class ApiKeyCreateRequest(BaseModel):
    name: str | None = None


async def _get_active_key(db: AsyncSession, user_id: uuid.UUID) -> UserApiKey | None:
    result = await db.execute(
        select(UserApiKey).where(
            UserApiKey.user_id == user_id,
            UserApiKey.revoked_at.is_(None),
        )
    )
    return result.scalar_one_or_none()


@router.get(
    "",
    summary="Get current API key status (prefix + metadata; no secret)",
    responses={404: {"description": "No active key"}},
    tags=["bot-api"],
)
async def get_api_key_status(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> ApiKeyStatus:
    key = await _get_active_key(db, user.id)
    if key is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="no_api_key")
    return ApiKeyStatus(
        id=key.id,
        prefix=key.key_prefix,
        name=key.name,
        created_at=key.created_at,
        last_used_at=key.last_used_at,
    )


@router.post(
    "",
    summary="Create a new API key (revokes existing key if present)",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
    tags=["bot-api"],
)
async def create_api_key(
    body: ApiKeyCreateRequest = ApiKeyCreateRequest(),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> ApiKeyCreated:
    existing = await _get_active_key(db, user.id)
    if existing is not None:
        existing.revoked_at = datetime.now(UTC)

    app_secret = settings.app_secret_key.get_secret_value()
    full_key, prefix, key_hash = generate_api_key(app_secret)

    new_key = UserApiKey(
        id=uuid.uuid4(),
        user_id=user.id,
        key_prefix=prefix,
        key_hash=key_hash,
        name=body.name,
    )
    db.add(new_key)
    await db.commit()
    await db.refresh(new_key)

    return ApiKeyCreated(
        id=new_key.id,
        prefix=prefix,
        name=new_key.name,
        created_at=new_key.created_at,
        full_key=full_key,
    )


@router.delete(
    "",
    summary="Revoke the active API key",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_csrf)],
    tags=["bot-api"],
)
async def revoke_api_key(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> None:
    key = await _get_active_key(db, user.id)
    if key is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="no_api_key")
    key.revoked_at = datetime.now(UTC)
    await db.commit()
