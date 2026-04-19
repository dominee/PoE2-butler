"""Trade-search payload + URL builder endpoints.

These endpoints are pure computation over a client-supplied :class:`Item`;
no state is mutated. They exist as a server-side entrypoint so the same code
path can be reused by the future Discord bot.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel, Field

from app.db.models import User
from app.deps import get_current_user
from app.domain.item import Item
from app.services.trade_url import build_exact_search, build_upgrade_search

router = APIRouter(prefix="/api/trade", tags=["trade"])


class TradeSearchRequest(BaseModel):
    mode: Literal["exact", "upgrade"]
    item: Item
    league: str | None = None
    tolerance_pct: float | None = Field(default=None, ge=0, le=500)


class TradeSearchResponse(BaseModel):
    mode: Literal["exact", "upgrade"]
    league: str
    url: str
    payload: dict
    tolerance_pct: float | None = None


@router.post("/search", summary="Build a trade search payload + URL")
async def trade_search(
    body: TradeSearchRequest = Body(...),
    user: User = Depends(get_current_user),
) -> TradeSearchResponse:
    tolerance = (
        body.tolerance_pct
        if body.tolerance_pct is not None
        else float(user.trade_tolerance_pct)
    )
    if body.mode == "exact":
        result = build_exact_search(body.item, tolerance_pct=tolerance, league=body.league)
        return TradeSearchResponse(
            mode="exact",
            league=result["league"],
            url=result["url"],
            payload=result["payload"],
            tolerance_pct=tolerance,
        )
    if body.mode == "upgrade":
        result = build_upgrade_search(body.item, league=body.league)
        return TradeSearchResponse(
            mode="upgrade",
            league=result["league"],
            url=result["url"],
            payload=result["payload"],
        )
    raise HTTPException(status_code=400, detail="unknown_mode")
