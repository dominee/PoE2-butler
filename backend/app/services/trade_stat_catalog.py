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
# Template keys use ``#`` from :func:`app.services.trade_url.parse_mod_line`.
# Values are GGG stat *hashes* (``…stat_<hash>``) from ``/api/trade2/data/stats``.
BUNDLED_TEMPLATE_TO_STAT_HASH: dict[str, str] = {
    "# to maximum Life": "3299347043",
    "#% to Fire Resistance": "3372524247",
    "#% increased Physical Damage": "1509134228",
}

_BUCKET_STAT_PREFIX: dict[str, str] = {
    "implicit": "implicit",
    "explicit": "explicit",
    "rune": "rune",
    "enchant": "enchant",
    # Bench crafts use explicit-style ids on the trade site today.
    "crafted": "explicit",
}

log = get_logger("app.services.trade_stat_catalog")

_CACHE_TTL_SEC = 24 * 3600


def _user_agent(settings: Settings) -> str:
    return (
        f"OAuth {settings.ggg_client_id}/{settings.app_version} "
        f"(contact: {settings.ggg_user_agent_contact}) {settings.ggg_user_agent_suffix}"
    )


def trade_search_user_agent(settings: Settings) -> str:
    """User-Agent for PoE2 trade metadata GET and search POST requests."""
    return _user_agent(settings)


def bundled_trade_stat_id(bucket: str, template: str) -> str | None:
    """Resolve a bundled numeric stat id for ``template`` in the given mod ``bucket``."""
    h = BUNDLED_TEMPLATE_TO_STAT_HASH.get(template)
    if not h:
        return None
    prefix = _BUCKET_STAT_PREFIX.get(bucket, "explicit")
    return f"{prefix}.stat_{h}"


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
                headers={
                    "User-Agent": trade_search_user_agent(settings),
                    "Accept": "application/json",
                },
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
    t = bundled_trade_stat_id("explicit", template)
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
