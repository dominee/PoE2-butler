"""Per-API-key sliding-window rate limiter (Redis).

Uses a simple counter + TTL approach (same pattern as share_ratelimit.py).
The window resets every 60 seconds; requests that exceed the cap receive HTTP 429.
"""

from __future__ import annotations

from fastapi import HTTPException, status
from redis.asyncio import Redis

_WINDOW_SECONDS = 60
_REDIS_KEY = "ratelimit:api_key:{prefix}"


async def enforce_api_key_rate_limit(redis: Redis, prefix: str, limit: int) -> None:
    """Raise HTTP 429 if the key identified by ``prefix`` has exceeded ``limit`` RPM."""
    key = _REDIS_KEY.format(prefix=prefix)
    n = await redis.incr(key)
    if n == 1:
        await redis.expire(key, _WINDOW_SECONDS)
    if n > limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="api_key_rate_limited",
            headers={"Retry-After": str(_WINDOW_SECONDS)},
        )
