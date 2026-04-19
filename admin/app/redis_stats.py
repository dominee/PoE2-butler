"""Redis and queue statistics helpers for the admin console."""

from __future__ import annotations

from functools import lru_cache

import httpx
from redis.asyncio import Redis

from admin.app.config import get_admin_settings


@lru_cache
def get_redis() -> Redis:
    return Redis.from_url(get_admin_settings().redis_url, decode_responses=True)


async def redis_summary() -> dict:
    redis = get_redis()
    info = await redis.info(section="memory")
    info_cpu = await redis.info(section="clients")
    keys = await redis.dbsize()
    return {
        "keys": keys,
        "used_memory_human": info.get("used_memory_human"),
        "used_memory_peak_human": info.get("used_memory_peak_human"),
        "maxmemory_human": info.get("maxmemory_human"),
        "connected_clients": info_cpu.get("connected_clients"),
    }


async def queue_summary() -> dict:
    """Report arq queue stats (queue length + in-progress)."""
    redis = get_redis()
    queued = await redis.zcard("arq:queue")
    in_progress = await redis.scard("arq:in-progress")
    return {"queued": queued, "in_progress": in_progress}


async def price_cache_summary() -> dict:
    """Count price keys and sample a few for display."""
    redis = get_redis()
    cursor = 0
    total = 0
    sample: list[str] = []
    while True:
        cursor, keys = await redis.scan(cursor=cursor, match="price:*", count=200)
        total += len(keys)
        if len(sample) < 10:
            sample.extend(keys[: 10 - len(sample)])
        if cursor == 0:
            break
    return {"keys": total, "sample": sample}


async def backend_health() -> dict:
    """Ping the backend's /healthz and /readyz endpoints."""
    settings = get_admin_settings()
    async with httpx.AsyncClient(base_url=settings.backend_base_url, timeout=3.0) as client:
        result: dict[str, int | str] = {}
        for path in ("/healthz", "/readyz"):
            try:
                resp = await client.get(path)
                result[path] = resp.status_code
            except httpx.HTTPError as exc:
                result[path] = f"error: {exc}"
        return result
