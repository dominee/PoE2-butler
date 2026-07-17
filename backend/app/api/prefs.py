"""User preferences endpoints: trade tolerance, valuable threshold, preferred league/character."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_session
from app.db.models import User
from app.deps import get_current_user_any, get_current_user_mutate

router = APIRouter(prefix="/api/prefs", tags=["prefs", "bot-api"])


class PrefsPatch(BaseModel):
    trade_tolerance_pct: int | None = Field(default=None, ge=0, le=500)
    preferred_league: str | None = None
    preferred_character_name: str | None = None
    valuable_threshold_chaos: int | None = Field(default=None, ge=0, le=1_000_000)


class PrefsResponse(BaseModel):
    trade_tolerance_pct: int
    preferred_league: str | None
    preferred_character_name: str | None
    valuable_threshold_chaos: int


def _serialize(user: User) -> PrefsResponse:
    return PrefsResponse(
        trade_tolerance_pct=user.trade_tolerance_pct,
        preferred_league=user.preferred_league,
        preferred_character_name=user.preferred_character_name,
        valuable_threshold_chaos=user.valuable_threshold_chaos,
    )


@router.get("", summary="Current user preferences")
async def get_prefs(user: User = Depends(get_current_user_any)) -> PrefsResponse:
    return _serialize(user)


@router.patch("", summary="Update user preferences")
async def patch_prefs(
    patch: PrefsPatch,
    user: User = Depends(get_current_user_mutate),
    db: AsyncSession = Depends(get_session),
) -> PrefsResponse:
    if patch.trade_tolerance_pct is not None:
        user.trade_tolerance_pct = patch.trade_tolerance_pct
    if patch.preferred_league is not None:
        user.preferred_league = patch.preferred_league or None
    if patch.preferred_character_name is not None:
        user.preferred_character_name = patch.preferred_character_name or None
    if patch.valuable_threshold_chaos is not None:
        user.valuable_threshold_chaos = patch.valuable_threshold_chaos
    await db.commit()
    return _serialize(user)
