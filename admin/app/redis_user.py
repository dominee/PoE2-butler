"""Redis keys related to a specific user (sessions, cooldowns, OAuth)."""

from __future__ import annotations

import json
from typing import Any

from redis.asyncio import Redis

from admin.app.config import get_admin_settings


async def _redis() -> Redis:
    return Redis.from_url(get_admin_settings().redis_url, decode_responses=True)


async def user_redis_state(user_id: str) -> dict[str, Any]:
    """Summarise Redis keys that affect login, refresh, and shares for one user."""
    r = await _redis()
    try:
        session_keys: list[str] = []
        async for key in r.scan_iter(match="sess:*", count=200):
            blob = await r.get(key)
            if not blob:
                continue
            try:
                data = json.loads(blob)
            except json.JSONDecodeError:
                continue
            if str(data.get("user_id") or "") == user_id:
                session_keys.append(key)

        cooldown_key = f"refresh:cooldown:{user_id}"
        cooldown_ttl = await r.ttl(cooldown_key)
        share_rl_key = f"ratelimit:item_share:{user_id}"
        share_rl_ttl = await r.ttl(share_rl_key)

        oauth_pending = 0
        async for _ in r.scan_iter(match="oauth:pending:*", count=100):
            oauth_pending += 1

        return {
            "session_count": len(session_keys),
            "session_keys_sample": session_keys[:5],
            "refresh_cooldown_ttl_sec": max(int(cooldown_ttl), 0)
            if cooldown_ttl and cooldown_ttl > 0
            else 0,
            "share_rate_limit_ttl_sec": max(int(share_rl_ttl), 0)
            if share_rl_ttl and share_rl_ttl > 0
            else 0,
            "oauth_pending_keys_scanned": oauth_pending,
        }
    finally:
        await r.aclose()
