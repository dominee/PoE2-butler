"""Submit PoE2 trade searches to GGG and obtain a short-lived search id for deep links."""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import quote

import httpx
from redis.asyncio import Redis

from app.config import Settings
from app.logging import get_logger
from app.services.third_party_ratelimit import (
    await_ggg_trade_slot,
    ggg_trade_mark_success,
    ggg_trade_register_429,
)
from app.services.trade_ggg_body import ggg_search_body_from_result_payload
from app.services.trade_stat_catalog import trade_search_user_agent

log = get_logger("app.services.trade_search_submit")


def trade_search_post_url(settings: Settings, league: str) -> str:
    """POST target: ``{trade_search_api_base}/{encoded_league}``."""
    base = settings.trade_search_api_base.rstrip("/")
    return f"{base}/{quote(league, safe='')}"


async def submit_trade_search(
    settings: Settings,
    league: str,
    result_payload: dict[str, Any],
    *,
    redis: Redis | None = None,
) -> tuple[str | None, dict[str, Any] | None, bool]:
    """POST a sanitized body to GGG; return ``(search_id, post_json, rate_limited)``.

    On HTTP 200, *post_json* is the parsed response body (includes ``id``, ``result``,
    ``total``). As of 2026, PoE2 trade2 returns the first page of listing id strings in
    ``POST`` ``result``; a follow-up ``GET`` for the same id often returns only
    ``id`` + ``query`` without ``result``, so callers must read ids from *post_json*.

    When *redis* is set, enforces :func:`await_ggg_trade_slot` and records 429 / success
    for the global GGG trade2 lock.
    """
    league = (league or "").strip()
    if not league:
        return None, None, False
    body = ggg_search_body_from_result_payload(result_payload)
    url = trade_search_post_url(settings, league)
    if redis is not None:
        await await_ggg_trade_slot(redis, settings)
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.post(
                url,
                json=body,
                headers={
                    "User-Agent": trade_search_user_agent(settings),
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
            )
    except (httpx.HTTPError, OSError) as exc:
        log.warning("trade_search.submit_transport_error", url=url, error=str(exc))
        return None, None, False

    if r.status_code == 429:
        if redis is not None:
            w = await ggg_trade_register_429(
                redis,
                settings,
                r.text,
                retry_after_header=r.headers.get("Retry-After"),
            )
            log.warning(
                "trade_search.submit_429",
                wait_registered_sec=w,
                body_preview=(r.text[:200] if r.text else ""),
            )
        else:
            log.warning(
                "trade_search.submit_http_error",
                url=url,
                status_code=429,
                body_preview=r.text[:500] if r.text else "",
            )
        return None, None, True

    if r.status_code != 200:
        log.warning(
            "trade_search.submit_http_error",
            url=url,
            status_code=r.status_code,
            body_preview=r.text[:500] if r.text else "",
        )
        return None, None, False

    try:
        data: dict[str, Any] = r.json()
    except json.JSONDecodeError:
        log.warning("trade_search.submit_bad_json", url=url)
        return None, None, False

    sid = data.get("id")
    if not isinstance(sid, str) or not sid.strip():
        log.warning("trade_search.submit_missing_id", url=url, keys=list(data.keys()))
        return None, None, False
    if redis is not None:
        await ggg_trade_mark_success(redis, settings)
    return sid.strip(), data, False
