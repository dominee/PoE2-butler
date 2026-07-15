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
from app.domain.item import Item, strip_runeforged_prefix_item
from app.logging import get_logger
from app.services.trade_listings import trade_listing_ids_from_search_post
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


async def _runeforged_base_type_fallback(
    item: Item,
    mode: str,
    post_body: dict | None,
    settings: Settings,
    league: str,
    tolerance: float,
    redis: Redis,
) -> tuple[str | None, dict | None]:
    """If the trade search returned 0 listings for a runeforged item, retry with the bare base type.

    Returns ``(search_id, result_dict)`` for the fallback, or ``(None, None)`` when the
    fallback is not applicable (item not runeforged, listings already found, rate-limited, etc.).
    """
    if post_body is None:
        return None, None
    _, total = trade_listing_ids_from_search_post(post_body)
    if total > 0:
        return None, None  # listings exist — no fallback needed

    fallback_item = strip_runeforged_prefix_item(item)
    if fallback_item is None:
        return None, None

    log.info(
        "trade_search.runeforged_fallback",
        mode=mode,
        original_base_type=item.base_type,
        fallback_base_type=fallback_item.base_type,
    )

    if mode == "exact":
        fb = build_exact_search(fallback_item, tolerance_pct=tolerance, league=league)
    elif mode == "upgrade":
        fb = build_upgrade_search(fallback_item, league=league)
    else:  # weighted_upgrade
        fb = build_weighted_upgrade_search(fallback_item, league=league)
    enrich_trade_payload_stat_ids(fb["payload"])
    if mode == "weighted_upgrade":
        fix_weight_group_floor(fb["payload"])
    fb_sid, _, _, _ = await submit_trade_search(settings, league, fb["payload"], redis=redis)
    return fb_sid, fb


def _resolve_trade_league(body_league: str | None, user: User) -> str:
    league = (body_league or user.preferred_league or "").strip()
    if not league:
        raise HTTPException(status_code=400, detail="league_required")
    return league


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
    league = _resolve_trade_league(body.league, user)
    await ensure_trade_stats_index(settings)
    if body.mode == "exact":
        result = build_exact_search(body.item, tolerance_pct=tolerance, league=league)
        enrich_trade_payload_stat_ids(result["payload"])
        search_id, post_body, _, _ = await submit_trade_search(
            settings, result["league"], result["payload"], redis=redis
        )
        if search_id:
            fb_sid, fb_result = await _runeforged_base_type_fallback(
                body.item, "exact", post_body, settings, league, tolerance, redis
            )
            if fb_sid and fb_result:
                search_id, result = fb_sid, fb_result
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
        result = build_upgrade_search(body.item, league=league)
        enrich_trade_payload_stat_ids(result["payload"])
        search_id, post_body, _, _ = await submit_trade_search(
            settings, result["league"], result["payload"], redis=redis
        )
        if search_id:
            fb_sid, fb_result = await _runeforged_base_type_fallback(
                body.item, "upgrade", post_body, settings, league, tolerance, redis
            )
            if fb_sid and fb_result:
                search_id, result = fb_sid, fb_result
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
        result = build_weighted_upgrade_search(body.item, league=league)
        enrich_trade_payload_stat_ids(result["payload"])
        fix_weight_group_floor(result["payload"])
        search_id, post_body, _, status_code = await submit_trade_search(
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
            fallback = build_upgrade_search(body.item, league=league)
            enrich_trade_payload_stat_ids(fallback["payload"])
            search_id, post_body, _, _ = await submit_trade_search(
                settings, fallback["league"], fallback["payload"], redis=redis
            )
            if search_id:
                fb_sid, fb_result = await _runeforged_base_type_fallback(
                    body.item, "upgrade", post_body, settings, league, tolerance, redis
                )
                if fb_sid and fb_result:
                    search_id, fallback = fb_sid, fb_result
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
        if search_id:
            fb_sid, fb_result = await _runeforged_base_type_fallback(
                body.item, "weighted_upgrade", post_body, settings, league, tolerance, redis
            )
            if fb_sid and fb_result:
                search_id, result = fb_sid, fb_result
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
