"""Current-user endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.db.models import User
from app.deps import get_current_user

router = APIRouter(prefix="/api/me", tags=["me"])


class MeResponse(BaseModel):
    id: str
    account_name: str
    realm: str
    preferred_league: str | None
    trade_tolerance_pct: int


@router.get("", summary="Current user")
async def me(user: User = Depends(get_current_user)) -> MeResponse:
    return MeResponse(
        id=str(user.id),
        account_name=user.ggg_account_name,
        realm=user.realm,
        preferred_league=user.preferred_league,
        trade_tolerance_pct=user.trade_tolerance_pct,
    )
