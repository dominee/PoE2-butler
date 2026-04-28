"""Lazy arq connection pool for API routes (enqueue only)."""

from __future__ import annotations

import asyncio
from typing import Any

from arq import create_pool
from arq.connections import RedisSettings

from app.config import get_settings

_pool: Any = None
_lock = asyncio.Lock()


async def get_arq_pool() -> Any:
    global _pool
    if _pool is not None:
        return _pool
    async with _lock:
        if _pool is None:
            _pool = await create_pool(RedisSettings.from_dsn(get_settings().redis_url))
    return _pool
