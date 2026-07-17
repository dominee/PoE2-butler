"""Manual snapshot refresh endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.ggg import GGGClient
from app.config import get_settings
from app.db.base import get_session
from app.db.models import User
from app.deps import (
    get_cipher,
    get_current_user_mutate,
    get_ggg_client,
    get_refresh_cooldown,
)
from app.security.crypto import TokenCipher
from app.security.sessions import RefreshCooldown
from app.services.snapshot import (
    delete_character_snapshots,
    refresh_character_gear_snapshots,
    refresh_user_snapshot,
)

router = APIRouter(prefix="/api/refresh", tags=["refresh"])


class RefreshResponse(BaseModel):
    profile: bool
    leagues: bool
    characters: bool
    errors: list[str] = []


@router.post(
    "",
    summary="Refresh snapshot data (no pricing jobs)",
    tags=["bot-api"],
)
async def refresh(
    league: str | None = Query(
        None,
        description=(
            "League whose stash tabs (and matching character gear) to refresh. "
            "Defaults to the account preferred league so the UI league selector "
            "and GET /api/activity?league=… stay aligned."
        ),
    ),
    user: User = Depends(get_current_user_mutate),
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

    settings = get_settings()
    api = settings.ggg_api_base_url.lower()
    # Poe.ninja full-list revalidate is mock-ggg only; real GGG uses /character/poe2 without it.
    is_mock = "mock-ggg" in api or "127.0.0.1" in api
    revalidate_list = is_mock

    stash_league = (league or "").strip() or (user.preferred_league or "").strip()

    # Keep stash snapshots in sync with the manual refresh button so the
    # activity panel (diff against prev_payload) gets fresh data too.
    outcome = await refresh_user_snapshot(
        session=db,
        user=user,
        ggg=ggg,
        cipher=cipher,
        include_stashes_for_league=stash_league or None,
        revalidate_character_list=revalidate_list,
    )
    captured = await delete_character_snapshots(db, user.id)
    if stash_league:
        await refresh_character_gear_snapshots(
            session=db,
            user=user,
            ggg=ggg,
            cipher=cipher,
            league=stash_league,
            captured_characters=captured,
        )
    await db.commit()
    return RefreshResponse(
        profile=outcome.profile,
        leagues=outcome.leagues,
        characters=outcome.characters,
        errors=outcome.errors or [],
    )
