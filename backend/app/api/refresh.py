"""Manual snapshot refresh endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.ggg import GGGClient
from app.db.base import get_session
from app.db.models import User
from app.deps import (
    get_cipher,
    get_current_user,
    get_ggg_client,
    get_refresh_cooldown,
    require_csrf,
)
from app.security.crypto import TokenCipher
from app.security.sessions import RefreshCooldown
from app.services.snapshot import refresh_user_snapshot

router = APIRouter(prefix="/api/refresh", tags=["refresh"])


class RefreshResponse(BaseModel):
    profile: bool
    leagues: bool
    characters: bool
    errors: list[str] = []


@router.post("", summary="Refresh snapshot data", dependencies=[Depends(require_csrf)])
async def refresh(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
    ggg: GGGClient = Depends(get_ggg_client),
    cipher: TokenCipher = Depends(get_cipher),
    cooldown: RefreshCooldown = Depends(get_refresh_cooldown),
) -> RefreshResponse:
    if not await cooldown.try_acquire(str(user.id)):
        retry_in = await cooldown.remaining(str(user.id))
        raise HTTPException(
            status_code=429,
            detail="cooldown",
            headers={"Retry-After": str(retry_in)},
        )

    # Keep stash snapshots in sync with the manual refresh button so the
    # activity panel (diff against prev_payload) gets fresh data too.
    outcome = await refresh_user_snapshot(
        session=db,
        user=user,
        ggg=ggg,
        cipher=cipher,
        include_stashes_for_league=user.preferred_league,
    )
    await db.commit()
    return RefreshResponse(
        profile=outcome.profile,
        leagues=outcome.leagues,
        characters=outcome.characters,
        errors=outcome.errors or [],
    )
