"""Throttling helpers for 3rd-party API calls (Redis).

Used from the arq worker and the API layer before GGG trade2 / poe.ninja, etc.
The GGG trade public API is strictly rate-limited: use :func:`await_ggg_trade_slot`
before every search POST / list GET / fetch GET, then :func:`ggg_trade_mark_success`
on HTTP 200. On HTTP 429, :func:`ggg_trade_register_429` sets a Redis lock for the
server-requested wait time (plus buffer) parsed from the JSON body.
"""

from __future__ import annotations

import asyncio
import math
import re

from redis.asyncio import Redis

from app.config import Settings

# Key prefix: ``tp3:{vendor}`` — one logical slot per job tick (fixed window).
KEY_POE_NINJA = "tp3:poe_ninja"
KEY_GGG_TRADE_META = "tp3:ggg_trade_data"
KEY_GGG_TRADE_FETCH = "tp3:ggg_trade_fetch"
KEY_GGG_TRADE_LOCK = "tp3:ggg_trade:lock"
KEY_GENERIC = "tp3:generic"
KEY_PRICE_ESTIMATE_SLOT_PREFIX = "tp3:price_estimate:slot:"

# TTL for a held estimate slot if a worker dies mid-job (seconds).
_PRICE_ESTIMATE_SLOT_TTL_SEC = 900

# Default minimum spacing between calls for hot loops (seconds).
_DEFAULT_INTERVAL = 0.35

_GGG_WAIT_RE = re.compile(r"Please wait (\d+)\s*seconds", re.IGNORECASE)


def parse_retry_after_header(value: str | None) -> int | None:
    """Parse ``Retry-After`` (seconds) from a GGG HTTP 429 response."""
    if not value:
        return None
    v = value.strip().split(",")[0].strip()
    try:
        n = int(v)
    except ValueError:
        return None
    return max(1, min(n, 86400))


def parse_ggg_rate_limit_wait_sec(body: str) -> int | None:
    """Parse ``Please wait N seconds`` from GGG JSON error body."""
    if not body:
        return None
    m = _GGG_WAIT_RE.search(body)
    if not m:
        return None
    try:
        return max(1, int(m.group(1)))
    except (TypeError, ValueError):
        return None


async def throttle(
    redis: Redis,
    key: str = KEY_GENERIC,
    *,
    min_interval_sec: float = _DEFAULT_INTERVAL,
) -> None:
    """Block until a new call is allowed (simple per-key lock with TTL)."""
    token = f"{key}:next"
    for _ in range(50):
        ok = await redis.set(token, "1", ex=max(1, int(min_interval_sec * 2)), nx=True)
        if ok:
            return
        await asyncio.sleep(min_interval_sec)
    # best-effort: do not block worker forever


async def await_ggg_trade_slot(redis: Redis, settings: Settings) -> None:
    """Block until the global GGG trade2 lock expires (spacing or 429 backoff)."""
    key = KEY_GGG_TRADE_LOCK
    while True:
        pttl = await redis.pttl(key)
        if pttl is None or pttl == -2:
            return
        if pttl == -1:
            await asyncio.sleep(0.5)
            continue
        if pttl <= 0:
            return
        await asyncio.sleep(min(pttl / 1000.0 + 0.02, 5.0))


async def ggg_trade_mark_success(redis: Redis, settings: Settings) -> None:
    """After a successful GGG trade2 response, enforce min spacing before the next call."""
    # GGG trade policy is strict (search/list/fetch share limits). Values like 0.55s from
    # mis-tuned env cause 429 storms; keep a hard floor so production safety wins over dev speed.
    min_gap = max(10.0, float(settings.ggg_trade_min_interval_sec))
    base = min_gap + float(settings.ggg_trade_extra_spacing_sec)
    ex = max(1, int(math.ceil(base)))
    await redis.set(KEY_GGG_TRADE_LOCK, "1", ex=ex)


async def ggg_trade_register_429(
    redis: Redis,
    settings: Settings,
    body: str,
    *,
    retry_after_header: str | None = None,
) -> int:
    """Set lock TTL from GGG JSON body and/or ``Retry-After`` (plus buffer), capped."""
    buf = int(settings.ggg_trade_429_buffer_sec)
    fb = int(settings.ggg_trade_429_fallback_sec)
    cap = int(settings.ggg_trade_429_max_wait_sec)
    body_w = parse_ggg_rate_limit_wait_sec(body)
    hdr_w = parse_retry_after_header(retry_after_header)
    parts = [x for x in (body_w, hdr_w) if x is not None]
    w0 = max(parts) if parts else fb
    total = min(cap, w0 + buf)
    await redis.set(KEY_GGG_TRADE_LOCK, "429", ex=max(1, total))
    return total


async def await_price_estimate_slot(redis: Redis, settings: Settings) -> str:
    """Block until one of the global hybrid price-estimate slots is free.

    Serializes GGG trade2 work across all ``price_estimate_item`` arq jobs and
    ``backfill_item_price_estimates`` inner loops so admin never shows many
    parallel ``running`` estimates exhausting rate limits.
    """
    limit = max(1, min(int(settings.pricing_max_concurrent_estimates), 8))
    poll = 0.35
    for _ in range(7200):
        for idx in range(limit):
            token = f"{KEY_PRICE_ESTIMATE_SLOT_PREFIX}{idx}"
            if await redis.set(token, "1", nx=True, ex=_PRICE_ESTIMATE_SLOT_TTL_SEC):
                return token
        await asyncio.sleep(poll)
    msg = "price_estimate_slot_timeout"
    raise TimeoutError(msg)


async def release_price_estimate_slot(redis: Redis, token: str) -> None:
    await redis.delete(token)
