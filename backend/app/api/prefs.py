"""User preferences endpoints: trade tolerance, valuable threshold, preferred league."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_session
from app.db.models import User
from app.deps import get_current_user, require_csrf

router = APIRouter(prefix="/api/prefs", tags=["prefs"])


class PrefsPatch(BaseModel):
    trade_tolerance_pct: int | None = Field(default=None, ge=0, le=500)
    preferred_league: str | None = None
    valuable_threshold_chaos: int | None = Field(default=None, ge=0, le=1_000_000)


class PrefsResponse(BaseModel):
    trade_tolerance_pct: int
    preferred_league: str | None
    valuable_threshold_chaos: int


def _serialize(user: User) -> PrefsResponse:
    return PrefsResponse(
        trade_tolerance_pct=user.trade_tolerance_pct,
        preferred_league=user.preferred_league,
        valuable_threshold_chaos=user.valuable_threshold_chaos,
    )


@router.get("", summary="Current user preferences")
async def get_prefs(user: User = Depends(get_current_user)) -> PrefsResponse:
    return _serialize(user)


@router.patch("", summary="Update user preferences", dependencies=[Depends(require_csrf)])
async def patch_prefs(
    patch: PrefsPatch,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> PrefsResponse:
    if patch.trade_tolerance_pct is not None:
        user.trade_tolerance_pct = patch.trade_tolerance_pct
    if patch.preferred_league is not None:
        user.preferred_league = patch.preferred_league or None
    if patch.valuable_threshold_chaos is not None:
        user.valuable_threshold_chaos = patch.valuable_threshold_chaos
    await db.commit()
    return _serialize(user)
