"""Operator-only backend routes invoked by the admin console."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.ggg import GGGClient
from app.config import Settings, get_settings
from app.db.base import get_session
from app.db.models import ItemShare, User
from app.deps import get_cipher, get_ggg_client, get_session_store
from app.security.crypto import TokenCipher
from app.security.sessions import SessionStore
from app.services.snapshot import (
    delete_character_snapshots,
    refresh_character_gear_snapshots,
    refresh_user_snapshot,
)

router = APIRouter(prefix="/api/admin", tags=["admin-ops"])


class AdminActionResponse(BaseModel):
    ok: bool
    detail: str = ""


async def require_admin_secret(
    settings: Settings = Depends(get_settings),
    secret: str | None = Header(default=None, alias="X-Admin-Internal-Secret"),
) -> None:
    expected = settings.admin_internal_secret.get_secret_value().strip()
    if not expected:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="admin_ops_disabled")
    if not secret or secret != expected:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")


@router.post(
    "/users/{user_id}/refresh",
    summary="Enqueue snapshot refresh for a user (operator)",
    dependencies=[Depends(require_admin_secret)],
)
async def admin_refresh_user(
    user_id: str,
    db: AsyncSession = Depends(get_session),
    ggg: GGGClient = Depends(get_ggg_client),
    cipher: TokenCipher = Depends(get_cipher),
) -> AdminActionResponse:
    try:
        uid = uuid.UUID(user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="invalid_user_id") from exc
    user = await db.get(User, uid)
    if user is None:
        raise HTTPException(status_code=404, detail="user_not_found")

    league = (user.preferred_league or "").strip()
    outcome = await refresh_user_snapshot(
        session=db,
        user=user,
        ggg=ggg,
        cipher=cipher,
        include_stashes_for_league=league or None,
    )
    captured = await delete_character_snapshots(db, user.id)
    if league:
        await refresh_character_gear_snapshots(
            session=db,
            user=user,
            ggg=ggg,
            cipher=cipher,
            league=league,
            captured_characters=captured,
        )
    await db.commit()
    errors = outcome.errors or []
    return AdminActionResponse(
        ok=not errors or outcome.characters or outcome.profile,
        detail="; ".join(errors) if errors else "refreshed",
    )


@router.post(
    "/users/{user_id}/logout",
    summary="Destroy all app sessions for a user (operator)",
    dependencies=[Depends(require_admin_secret)],
)
async def admin_logout_user(
    user_id: str,
    sessions: SessionStore = Depends(get_session_store),
) -> AdminActionResponse:
    n = await sessions.destroy_all_for_user(user_id)
    return AdminActionResponse(ok=True, detail=f"sessions_destroyed={n}")


@router.post(
    "/shares/{share_id}/revoke",
    summary="Revoke a public item share (operator)",
    dependencies=[Depends(require_admin_secret)],
)
async def admin_revoke_share(
    share_id: str,
    db: AsyncSession = Depends(get_session),
) -> AdminActionResponse:
    try:
        sid = uuid.UUID(share_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="invalid_share_id") from exc
    row = await db.get(ItemShare, sid)
    if row is None:
        raise HTTPException(status_code=404, detail="share_not_found")
    if row.revoked_at is None:
        row.revoked_at = datetime.now(UTC)
        await db.commit()
    return AdminActionResponse(ok=True, detail="revoked")
