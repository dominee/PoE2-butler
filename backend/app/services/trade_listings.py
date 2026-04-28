"""GGG PoE2 trade search: list ids + fetch listing JSON and chaos prices.

Uses the public JSON API (no OAuth). See :doc:`docs/trade_deeplinks.md`.
"""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import quote

import httpx

from app.config import Settings
from app.logging import get_logger
from app.services.trade_stat_catalog import trade_search_user_agent

log = get_logger("app.services.trade_listings")

# GGG often returns a handful of ids per ``fetch`` call.
_FETCH_BATCH = 8
_MAX_FETCH_IDS = 40


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
    if "chaos" in c:
        return amount
    if c in chaos_per_name:
        return amount * chaos_per_name[c]
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


async def trade_search_list_result(
    settings: Settings,
    league: str,
    search_id: str,
    *,
    start: int = 0,
) -> tuple[int, list[str]]:
    """GET ``/api/trade2/search/{league}/{id}`` — returns ``(total, result_ids)``."""
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
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            r = await client.get(
                url,
                params=params or None,
                headers=h_get,
            )
    except (httpx.HTTPError, OSError) as exc:
        log.warning("trade_listings.search_get_failed", error=str(exc))
        return 0, []

    if r.status_code != 200:
        log.warning("trade_listings.search_get_http", status_code=r.status_code, text=r.text[:400])
        return 0, []
    try:
        data: dict[str, Any] = r.json()
    except json.JSONDecodeError:
        return 0, []
    total = int(data.get("total") or 0)
    raw = data.get("result")
    if not isinstance(raw, list):
        return total, []
    out = [x for x in raw if isinstance(x, str) and x.strip()]
    return total, out


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
) -> list[dict[str, Any]]:
    """GET ``/api/trade2/fetch/{ids}?query=search_id`` — returns list of result dicts."""
    if not item_ids:
        return []
    base = _trade_fetch_base_url(settings)
    # ids joined by comma; URL-encode each? PoE uses hex without extra encoding.
    part = ",".join(item_ids[:_FETCH_BATCH])
    url = f"{base}/fetch/{part}"
    ua = trade_search_user_agent(settings)
    h_get = {"User-Agent": ua, "Accept": "application/json"}
    try:
        async with httpx.AsyncClient(timeout=25.0) as client:
            r = await client.get(
                url,
                params={"query": search_id},
                headers=h_get,
            )
    except (httpx.HTTPError, OSError) as exc:
        log.warning("trade_listings.fetch_failed", error=str(exc))
        return []

    if r.status_code != 200:
        log.warning("trade_listings.fetch_http", status_code=r.status_code, text=r.text[:400])
        return []
    try:
        data: dict[str, Any] = r.json()
    except json.JSONDecodeError:
        return []
    res = data.get("result")
    if not isinstance(res, list):
        return []
    return [x for x in res if isinstance(x, dict)]


async def sample_median_listing_chaos(
    settings: Settings,
    league: str,
    search_id: str,
    chaos_per_name: dict[str, float],
    *,
    min_samples: int = 5,
    cap_ids: int = 32,
) -> tuple[float, int]:
    """First search page + batched fetches; return (median, sample_count)."""
    total, ids = await trade_search_list_result(settings, league, search_id)
    if not ids:
        return 0.0, 0
    take = min(len(ids), cap_ids, _MAX_FETCH_IDS)
    if take < 1:
        return 0.0, 0
    all_prices: list[float] = []
    for off in range(0, take, _FETCH_BATCH):
        chunk = ids[off : off + _FETCH_BATCH]
        rows = await trade_fetch_listings(settings, league, search_id, chunk)
        for row in rows:
            v = listing_chaos_value(row, chaos_per_name)
            if v is not None and v > 0:
                all_prices.append(v)
        if len(all_prices) >= min_samples:
            break
    if not all_prices:
        return 0.0, 0
    return median_chaos(all_prices), len(all_prices)
