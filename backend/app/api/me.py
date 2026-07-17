"""Current-user endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.config import Settings, get_settings
from app.db.models import User
from app.deps import get_current_user_any
from app.domain.capabilities import Capabilities, capabilities_from_settings

router = APIRouter(prefix="/api/me", tags=["me"])


class MeResponse(BaseModel):
    id: str
    account_name: str
    realm: str
    preferred_league: str | None
    trade_tolerance_pct: int
    capabilities: Capabilities


@router.get("", summary="Current user")
async def me(
    user: User = Depends(get_current_user_any),
    settings: Settings = Depends(get_settings),
) -> MeResponse:
    return MeResponse(
        id=str(user.id),
        account_name=user.ggg_account_name,
        realm=user.realm,
        preferred_league=user.preferred_league,
        trade_tolerance_pct=user.trade_tolerance_pct,
        capabilities=capabilities_from_settings(settings),
    )
