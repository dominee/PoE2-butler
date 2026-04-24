"""Per-user rate limit for creating public item share links (Redis)."""

from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from redis.asyncio import Redis

# Documented in AGENTS / INSTRUCTIONS: tune without new infra.
SHARE_CREATE_LIMIT_PER_HOUR = 10
SHARE_LIMIT_WINDOW_SECONDS = 3600
SHARE_REDIS_KEY = "ratelimit:item_share:{user_id}"


async def enforce_share_create_limit(redis: Redis, user_id: uuid.UUID) -> None:
    key = SHARE_REDIS_KEY.format(user_id=user_id)
    n = await redis.incr(key)
    if n == 1:
        await redis.expire(key, SHARE_LIMIT_WINDOW_SECONDS)
    if n > SHARE_CREATE_LIMIT_PER_HOUR:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="share_create_rate_limited",
        )
