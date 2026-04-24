"""Throttling helpers for 3rd-party API calls (Redis).

Used from the arq worker and (optionally) the API layer before fan-out to
poe.ninja, trade filter metadata, etc. This is the product's answer to
INSTRUCTIONS § "message queue" for rate-limited partners: the job queue is arq;
per-vendor throttling is implemented here without a second broker.
"""

from __future__ import annotations

import asyncio

from redis.asyncio import Redis

# Key prefix: ``tp3:{vendor}`` — one logical slot per job tick (fixed window).
KEY_POE_NINJA = "tp3:poe_ninja"
KEY_GGG_TRADE_META = "tp3:ggg_trade_data"
KEY_GENERIC = "tp3:generic"

# Default minimum spacing between calls for hot loops (seconds).
_DEFAULT_INTERVAL = 0.35


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
