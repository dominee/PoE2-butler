"""GGG PoE2 trade search: list ids + fetch listing JSON and chaos prices.

Uses the public JSON API (no OAuth). See :doc:`docs/trade_deeplinks.md`.
"""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import quote

import httpx
from redis.asyncio import Redis

from app.config import Settings
from app.logging import get_logger
from app.services.third_party_ratelimit import (
    await_ggg_trade_slot,
    ggg_trade_mark_success,
    ggg_trade_register_429,
)
from app.services.trade_stat_catalog import trade_search_user_agent

log = get_logger("app.services.trade_listings")

# GGG often returns a handful of ids per ``fetch`` call.
_FETCH_BATCH = 8
_MAX_FETCH_IDS = 40


def trade_currency_chaos_fallback(settings: Settings) -> dict[str, float]:
    """GGG trade ``listing.price.currency`` uses compact ids (e.g. ``transmute``).

    When poe.ninja is unavailable, listings are still priced in these orbs; approximate
    chaos using configured divine/exalt anchors. Ninja ratios override via merge.
    """
    cdiv = float(settings.trade_listing_divine_to_chaos)
    cex = max(float(settings.trade_listing_exalt_to_chaos), 1e-6)

    def per_ex(parts_for_one_ex: float) -> float:
        return max(cex / max(parts_for_one_ex, 1e-6), 1e-9)

    return {
        "chaos": 1.0,
        "chaos orb": 1.0,
        "greater-chaos-orb": 1.12,
        "perfect-chaos-orb": 1.28,
        "divine": cdiv,
        "divine orb": cdiv,
        "exalted": cex,
        "exalted orb": cex,
        "greater-exalted-orb": cex * 1.12,
        "perfect-exalted-orb": cex * 1.28,
        "transmute": per_ex(400),
        "greater-orb-of-transmutation": per_ex(320),
        "perfect-orb-of-transmutation": per_ex(260),
        "aug": per_ex(120),
        "greater-orb-of-augmentation": per_ex(100),
        "perfect-orb-of-augmentation": per_ex(85),
        "chance": per_ex(22),
        "alch": per_ex(8),
        "regal": per_ex(4),
        "greater-regal-orb": per_ex(3.5),
        "perfect-regal-orb": per_ex(3.0),
        "vaal": per_ex(2.2),
        "annul": cex * 0.42,
        "artificers": per_ex(6),
        "wisdom": per_ex(900),
        "scrap": per_ex(220),
        "whetstone": per_ex(260),
        "etcher": per_ex(32),
        "bauble": per_ex(58),
        "gcp": per_ex(1.15),
        "lesser-jewellers-orb": per_ex(26),
        "greater-jewellers-orb": per_ex(22),
        "perfect-jewellers-orb": per_ex(18),
        "transmutation-shard": per_ex(4000),
        "chance-shard": per_ex(220),
        "regal-shard": per_ex(44),
        "artificers-shard": per_ex(60),
        "fracturing-orb": cex * 2.0,
        "mirror": cex * 8000.0,
        "hinekoras-lock": cex * 5.0,
    }


def median_chaos(values: list[float]) -> float:
    s = sorted(values)
    n = len(s)
    if n == 0:
        return 0.0
    m = n // 2
    if n % 2:
        return s[m]
    return (s[m - 1] + s[m]) / 2.0


def _match_currency_to_chaos(
    currency: str, chaos_per_name: dict[str, float], amount: float
) -> float | None:
    c = (currency or "").lower().strip()
    if not c or amount < 0:
        return None
    if c in chaos_per_name:
        return amount * chaos_per_name[c]
    if c == "chaos" or c == "chaos orb":
        return amount
    for name, v in chaos_per_name.items():
        if not name:
            continue
        if name in c or c in name.replace(" ", ""):
            return amount * v
    return None


def listing_chaos_value(entry: dict[str, Any], chaos_per_name: dict[str, float]) -> float | None:
    """Parse chaos equivalent from a single ``/fetch`` result object."""
    li = entry.get("listing")
    if not isinstance(li, dict):
        return None
    price = li.get("price")
    if not isinstance(price, dict):
        return None
    cur = str(price.get("currency") or price.get("type") or "")
    amt = price.get("amount")
    if amt is None:
        return None
    try:
        a = float(amt)
    except (TypeError, ValueError):
        return None
    return _match_currency_to_chaos(cur, chaos_per_name, a)


def trade_listing_ids_from_search_post(post: dict[str, Any] | None) -> tuple[list[str], int]:
    """Parse ``result`` (listing id strings) and ``total`` from a trade2 **POST** response.

    PoE2 returns the first page of ids here; a follow-up ``GET`` for the same search id
    may omit ``result`` (see :doc:`docs/trade_deeplinks.md`).
    """
    if not isinstance(post, dict):
        return [], 0
    total = int(post.get("total") or 0)
    raw = post.get("result")
    if not isinstance(raw, list):
        return [], total
    ids = [x for x in raw if isinstance(x, str) and x.strip()]
    return ids, total


async def trade_search_list_result(
    settings: Settings,
    league: str,
    search_id: str,
    *,
    start: int = 0,
    redis: Redis | None = None,
) -> tuple[int, list[str], bool, int]:
    """GET ``/api/trade2/search/{league}/{id}``.

    Returns ``(total, result_ids, rate_limited, page_slot_count)`` where *page_slot_count*
    is ``len(result)`` from JSON (used to advance the ``start`` offset). GGG may include
    ``null`` slots for removed listings — string ids may be empty while *total* > 0.
    """
    base = settings.trade_search_api_base.rstrip("/")
    # trade_search_api_base is .../search — list endpoint is same host + path .../search/league/id
    # Path is: {api_base}/../ but actually search base is `.../api/trade2/search`
    # So full URL: `.../api/trade2/search/{league}/{search_id}`
    url = f"{base}/{quote(league, safe='')}/{search_id}"
    params: dict[str, int] = {}
    if start:
        params["start"] = start
    ua = trade_search_user_agent(settings)
    h_get = {"User-Agent": ua, "Accept": "application/json"}
    if redis is not None:
        await await_ggg_trade_slot(redis, settings)
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            r = await client.get(
                url,
                params=params or None,
                headers=h_get,
            )
    except (httpx.HTTPError, OSError) as exc:
        log.warning("trade_listings.search_get_failed", error=str(exc))
        return 0, [], False, 0

    if r.status_code == 429:
        if redis is not None:
            await ggg_trade_register_429(
                redis,
                settings,
                r.text,
                retry_after_header=r.headers.get("Retry-After"),
            )
        log.warning("trade_listings.search_get_429", text=r.text[:400] if r.text else "")
        return 0, [], True, 0

    if r.status_code != 200:
        log.warning("trade_listings.search_get_http", status_code=r.status_code, text=r.text[:400])
        return 0, [], False, 0
    if redis is not None:
        await ggg_trade_mark_success(redis, settings)
    try:
        data: dict[str, Any] = r.json()
    except json.JSONDecodeError:
        return 0, [], False, 0
    total = int(data.get("total") or 0)
    raw = data.get("result")
    if not isinstance(raw, list):
        return total, [], False, 0
    page_len = len(raw)
    out = [x for x in raw if isinstance(x, str) and x.strip()]
    return total, out, False, page_len


async def trade_search_collect_string_ids(
    settings: Settings,
    league: str,
    search_id: str,
    *,
    redis: Redis | None = None,
    max_pages: int = 30,
) -> tuple[int, list[str], bool]:
    """Paginate list GET until at least one fetchable listing id or offsets are exhausted.

    The trade site interleaves sold/removed rows as JSON ``null``; the first window can
    contain no string ids even when ``total`` is large.
    """
    start = 0
    last_total = 0
    collected: list[str] = []
    for page in range(max_pages):
        total, chunk, list_rl, page_len = await trade_search_list_result(
            settings, league, search_id, start=start, redis=redis
        )
        last_total = total
        if list_rl:
            return total, collected, True
        collected.extend(chunk)
        if collected:
            return total, collected, False
        if total == 0:
            return 0, [], False
        step = page_len if page_len > 0 else 10
        start += step
        if start >= total:
            return total, [], False
    return last_total, [], False


def _trade_fetch_base_url(settings: Settings) -> str:
    """``…/api/trade2`` from ``trade_search_api_base`` default ``…/search``."""
    b = settings.trade_search_api_base.rstrip("/")
    if b.endswith("/search"):
        return b[: -len("/search")]
    return b.replace("/search", "")


async def trade_fetch_listings(
    settings: Settings,
    league: str,
    search_id: str,
    item_ids: list[str],
    *,
    redis: Redis | None = None,
) -> tuple[list[dict[str, Any]], bool]:
    """GET fetch for listing JSON — returns (result dicts, rate_limited)."""
    if not item_ids:
        return [], False
    base = _trade_fetch_base_url(settings)
    # ids joined by comma; URL-encode each? PoE uses hex without extra encoding.
    part = ",".join(item_ids[:_FETCH_BATCH])
    url = f"{base}/fetch/{part}"
    ua = trade_search_user_agent(settings)
    h_get = {"User-Agent": ua, "Accept": "application/json"}
    if redis is not None:
        await await_ggg_trade_slot(redis, settings)
    try:
        async with httpx.AsyncClient(timeout=25.0) as client:
            r = await client.get(
                url,
                params={"query": search_id},
                headers=h_get,
            )
    except (httpx.HTTPError, OSError) as exc:
        log.warning("trade_listings.fetch_failed", error=str(exc))
        return [], False

    if r.status_code == 429:
        if redis is not None:
            await ggg_trade_register_429(
                redis,
                settings,
                r.text,
                retry_after_header=r.headers.get("Retry-After"),
            )
        log.warning("trade_listings.fetch_429", text=r.text[:400] if r.text else "")
        return [], True

    if r.status_code != 200:
        log.warning("trade_listings.fetch_http", status_code=r.status_code, text=r.text[:400])
        return [], False
    if redis is not None:
        await ggg_trade_mark_success(redis, settings)
    try:
        data: dict[str, Any] = r.json()
    except json.JSONDecodeError:
        return [], False
    res = data.get("result")
    if not isinstance(res, list):
        return [], False
    return [x for x in res if isinstance(x, dict)], False


async def sample_median_listing_chaos(
    settings: Settings,
    league: str,
    search_id: str,
    chaos_per_name: dict[str, float],
    *,
    min_samples: int = 5,
    cap_ids: int = 32,
    redis: Redis | None = None,
    list_ids: list[str] | None = None,
) -> tuple[float, int, bool]:
    """Batched fetches; return ``(median, sample_count, rate_limited)``.

    When *list_ids* is set (caller already ran list pagination), skip the
    duplicate list GET — same policy bucket as search POST / fetch.
    """
    if list_ids is not None:
        ids = [x for x in list_ids if isinstance(x, str) and x.strip()]
        list_rl = False
    else:
        _total, ids, list_rl = await trade_search_collect_string_ids(
            settings, league, search_id, redis=redis
        )
    if list_rl:
        return 0.0, 0, True
    if not ids:
        return 0.0, 0, False
    take = min(len(ids), cap_ids, _MAX_FETCH_IDS)
    if take < 1:
        return 0.0, 0, False
    all_prices: list[float] = []
    for off in range(0, take, _FETCH_BATCH):
        chunk = ids[off : off + _FETCH_BATCH]
        rows, fetch_rl = await trade_fetch_listings(
            settings, league, search_id, chunk, redis=redis
        )
        if fetch_rl:
            return 0.0, 0, True
        for row in rows:
            v = listing_chaos_value(row, chaos_per_name)
            if v is not None and v > 0:
                all_prices.append(v)
        if len(all_prices) >= min_samples:
            break
    if not all_prices:
        return 0.0, 0, False
    return median_chaos(all_prices), len(all_prices), False
