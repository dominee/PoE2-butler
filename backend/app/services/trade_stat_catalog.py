"""Fetch/cache PoE2 trade-site filter + stat metadata for stat-id-based searches.

Falls back to an empty cache (and a tiny bundled map for tests) when the
public endpoint is unreachable. Used by :mod:`app.services.trade_url` and
background job :func:`app.workers.arq_worker.refresh_trade_filter_catalog`.
"""

from __future__ import annotations

import json

import httpx
from redis.asyncio import Redis

from app.config import Settings
from app.logging import get_logger

CATALOG_REDIS_KEY = "trade:filter_catalog:poe2:raw"
# Bundled hand-picked examples; extend as real ids are discovered from a successful fetch.
BUNDLED_TEMPLATE_TO_STAT_ID: dict[str, str] = {
    # Template keys use ``#`` from :func:`app.services.trade_url.parse_mod_line`.
    "# to maximum Life": "explicit.stat_2376",
    "#% to Fire Resistance": "explicit.stat_1180",
    "#% increased Physical Damage": "explicit.stat_1234",
}

log = get_logger("app.services.trade_stat_catalog")

_CACHE_TTL_SEC = 24 * 3600


def _user_agent(settings: Settings) -> str:
    return (
        f"OAuth {settings.ggg_client_id}/{settings.app_version} "
        f"(contact: {settings.ggg_user_agent_contact}) {settings.ggg_user_agent_suffix}"
    )


async def refresh_if_stale(redis: Redis, settings: Settings) -> int:
    """If Redis has no fresh catalog, attempt HTTP download. Returns byte length stored."""
    if await redis.get(CATALOG_REDIS_KEY):
        return 0
    url = settings.trade_filter_data_url
    if not url:
        await _store_fallback(redis)
        return 0
    try:
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.get(
                url,
                headers={"User-Agent": _user_agent(settings), "Accept": "application/json"},
            )
        if r.status_code == 200 and r.text:
            await redis.setex(CATALOG_REDIS_KEY, _CACHE_TTL_SEC, r.text)
            return len(r.text)
    except Exception as exc:  # noqa: BLE001
        log.warning("catalog.fetch_failed", url=url, error=str(exc))
    await _store_fallback(redis)
    return 0


async def _store_fallback(redis: Redis) -> None:
    await redis.setex(
        CATALOG_REDIS_KEY, _CACHE_TTL_SEC, json.dumps({"ok": False, "bundled_only": True})
    )


async def template_to_stat_id(redis: Redis, template: str) -> str | None:
    """Map a mod ``template`` (``#`` placeholders) to a trade stat id if known."""
    if not template:
        return None
    t = BUNDLED_TEMPLATE_TO_STAT_ID.get(template)
    if t:
        return t
    raw = await redis.get(CATALOG_REDIS_KEY)
    if not raw or raw == "{}":
        return None
    try:
        _ = json.loads(raw)
    except json.JSONDecodeError:
        return None
    # Full parsing of the GGG filter tree is not implemented here; bundled map wins.
    return None
