"""Redis and queue statistics helpers for the admin console."""

from __future__ import annotations

import json
import time
from functools import lru_cache
from typing import Any

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
    info_stats = await redis.info(section="stats")
    key_count = await redis.dbsize()
    return {
        "key_count": key_count,
        "used_memory_human": info.get("used_memory_human"),
        "used_memory_peak_human": info.get("used_memory_peak_human"),
        "maxmemory_human": info.get("maxmemory_human"),
        "connected_clients": info_cpu.get("connected_clients"),
        "evicted_keys": info_stats.get("evicted_keys"),
        "expired_keys": info_stats.get("expired_keys"),
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
    return {"key_count": total, "sample": sample}


def parse_health_body(status_code: int, text: str) -> dict[str, Any]:
    out: dict[str, Any] = {"status_code": status_code, "version": None, "status": None}
    if status_code != 200:
        return out
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, TypeError, ValueError):
        return out
    if isinstance(data, dict):
        if "version" in data:
            out["version"] = data.get("version")
        if "status" in data:
            out["status"] = data.get("status")
    return out


async def backend_health() -> dict[str, dict[str, Any]]:
    """Ping the backend's /healthz and /readyz; include latency and JSON fields when present."""
    settings = get_admin_settings()
    result: dict[str, dict[str, Any]] = {}
    async with httpx.AsyncClient(base_url=settings.backend_base_url, timeout=3.0) as client:
        for path in ("/healthz", "/readyz"):
            t0 = time.perf_counter()
            try:
                resp = await client.get(path)
                elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 2)
                parsed = parse_health_body(resp.status_code, resp.text)
                result[path] = {
                    "status_code": resp.status_code,
                    "latency_ms": elapsed_ms,
                    "version": parsed.get("version"),
                    "body_status": parsed.get("status"),
                    "error": None,
                }
            except httpx.HTTPError as exc:
                elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 2)
                result[path] = {
                    "status_code": None,
                    "latency_ms": elapsed_ms,
                    "version": None,
                    "body_status": None,
                    "error": str(exc),
                }
    return result


def probe_ok(probe: dict[str, Any]) -> bool:
    code = probe.get("status_code")
    return code == 200 and probe.get("error") is None
