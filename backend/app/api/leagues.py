"""Leagues endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_session
from app.db.models import SnapshotKind, User
from app.deps import get_current_user
from app.domain.league import League, parse_leagues, pick_current_league
from app.services.snapshot import get_latest_snapshot

router = APIRouter(prefix="/api/leagues", tags=["leagues"])


class LeaguesResponse(BaseModel):
    leagues: list[League]
    current: str | None
    preferred: str | None


@router.get("", summary="Leagues known to this user")
async def leagues(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> LeaguesResponse:
    snap = await get_latest_snapshot(db, user.id, SnapshotKind.LEAGUES)
    parsed: list[League] = []
    if snap is not None:
        parsed = parse_leagues(snap.payload)
    return LeaguesResponse(
        leagues=parsed,
        current=pick_current_league(parsed),
        preferred=user.preferred_league,
    )
