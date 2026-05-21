"""Trade-search payload + URL builder endpoints.

These endpoints are pure computation over a client-supplied :class:`Item`;
no state is mutated. They exist as a server-side entrypoint so the same code
path can be reused by the future Discord bot.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel, Field
from redis.asyncio import Redis

from app.config import Settings, get_settings
from app.db.models import User
from app.deps import get_current_user, get_redis
from app.domain.item import Item
from app.logging import get_logger
from app.services.trade_search_submit import submit_trade_search
from app.services.trade_stat_index import enrich_trade_payload_stat_ids, ensure_trade_stats_index
from app.services.trade_url import (
    build_exact_search,
    build_trade_url_with_search_id,
    build_upgrade_search,
    build_weighted_upgrade_search,
    fix_weight_group_floor,
)

router = APIRouter(prefix="/api/trade", tags=["trade"])

log = get_logger("app.api.trade")


class TradeSearchRequest(BaseModel):
    mode: Literal["exact", "upgrade", "weighted_upgrade"]
    item: Item
    league: str | None = None
    tolerance_pct: float | None = Field(default=None, ge=0, le=500)


class TradeSearchResponse(BaseModel):
    mode: Literal["exact", "upgrade", "weighted_upgrade"]
    league: str
    url: str
    payload: dict
    tolerance_pct: float | None = None


@router.post("/search", summary="Build a trade search payload + URL")
async def trade_search(
    body: TradeSearchRequest = Body(...),
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    redis: Redis = Depends(get_redis),
) -> TradeSearchResponse:
    tolerance = (
        body.tolerance_pct if body.tolerance_pct is not None else float(user.trade_tolerance_pct)
    )
    await ensure_trade_stats_index(settings)
    if body.mode == "exact":
        result = build_exact_search(body.item, tolerance_pct=tolerance, league=body.league)
        enrich_trade_payload_stat_ids(result["payload"])
        search_id, _, _, _ = await submit_trade_search(
            settings, result["league"], result["payload"], redis=redis
        )
        url = (
            build_trade_url_with_search_id(result["league"], search_id)
            if search_id
            else result["url"]
        )
        return TradeSearchResponse(
            mode="exact",
            league=result["league"],
            url=url,
            payload=result["payload"],
            tolerance_pct=tolerance,
        )
    if body.mode == "upgrade":
        result = build_upgrade_search(body.item, league=body.league)
        enrich_trade_payload_stat_ids(result["payload"])
        search_id, _, _, _ = await submit_trade_search(
            settings, result["league"], result["payload"], redis=redis
        )
        url = (
            build_trade_url_with_search_id(result["league"], search_id)
            if search_id
            else result["url"]
        )
        return TradeSearchResponse(
            mode="upgrade",
            league=result["league"],
            url=url,
            payload=result["payload"],
        )
    if body.mode == "weighted_upgrade":
        result = build_weighted_upgrade_search(body.item, league=body.league)
        enrich_trade_payload_stat_ids(result["payload"])
        fix_weight_group_floor(result["payload"])
        search_id, _, _, status_code = await submit_trade_search(
            settings, result["league"], result["payload"], redis=redis
        )
        if not search_id and status_code == 400:
            # GGG's anonymous trade API rejects weight-group queries as "too complex".
            # Fall back to the regular min-value upgrade search so the user still gets
            # a working trade URL instead of the base search page.
            log.info(
                "trade_search.weighted_upgrade_fallback",
                reason="ggg_400_too_complex",
                league=result["league"],
            )
            fallback = build_upgrade_search(body.item, league=body.league)
            enrich_trade_payload_stat_ids(fallback["payload"])
            search_id, _, _, _ = await submit_trade_search(
                settings, fallback["league"], fallback["payload"], redis=redis
            )
            url = (
                build_trade_url_with_search_id(fallback["league"], search_id)
                if search_id
                else fallback["url"]
            )
            return TradeSearchResponse(
                mode="weighted_upgrade",
                league=fallback["league"],
                url=url,
                payload=fallback["payload"],
            )
        url = (
            build_trade_url_with_search_id(result["league"], search_id)
            if search_id
            else result["url"]
        )
        return TradeSearchResponse(
            mode="weighted_upgrade",
            league=result["league"],
            url=url,
            payload=result["payload"],
        )
    raise HTTPException(status_code=400, detail="unknown_mode")
