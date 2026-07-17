"""Leagues endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.base import get_session
from app.db.models import SnapshotKind, User
from app.deps import get_current_user_any
from app.domain.character import parse_summaries
from app.domain.league import (
    League,
    parse_leagues,
    pick_league_from_characters,
    resolve_leagues_current,
)
from app.services.snapshot import get_latest_snapshot

router = APIRouter(prefix="/api/leagues", tags=["leagues"])


class LeaguesResponse(BaseModel):
    leagues: list[League]
    current: str | None
    preferred: str | None


@router.get("", summary="Leagues known to this user")
async def leagues(
    user: User = Depends(get_current_user_any),
    db: AsyncSession = Depends(get_session),
) -> LeaguesResponse:
    settings = get_settings()
    effective_preferred = user.preferred_league or settings.ggg_default_league or None

    inferred_from_characters: str | None = None
    chars_snap = await get_latest_snapshot(db, user.id, SnapshotKind.CHARACTERS)

    snap = await get_latest_snapshot(db, user.id, SnapshotKind.LEAGUES)
    parsed: list[League] = []
    if snap is not None:
        parsed = parse_leagues(snap.payload)
    if not parsed and chars_snap is not None:
        summaries = parse_summaries(chars_snap.payload)
        inferred_from_characters = pick_league_from_characters(summaries)
        display_current = resolve_leagues_current(
            [],
            effective_preferred,
            inferred_from_characters=inferred_from_characters,
            default_league=settings.ggg_default_league or None,
        )
        seen: set[str] = set()
        for c in summaries:
            if c.league and c.league not in seen:
                seen.add(c.league)
                parsed.append(
                    League(
                        id=c.league,
                        current=(c.league == display_current),
                    )
                )
    if not parsed and settings.ggg_default_league:
        parsed.append(
            League(
                id=settings.ggg_default_league,
                current=True,
            )
        )
    if inferred_from_characters is None and chars_snap is not None:
        inferred_from_characters = pick_league_from_characters(parse_summaries(chars_snap.payload))
    return LeaguesResponse(
        leagues=parsed,
        current=resolve_leagues_current(
            parsed,
            effective_preferred,
            inferred_from_characters=inferred_from_characters,
            default_league=settings.ggg_default_league or None,
        ),
        preferred=effective_preferred,
    )
