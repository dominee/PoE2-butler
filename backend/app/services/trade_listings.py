"""GGG PoE2 trade search: list ids + fetch listing JSON and chaos prices.

Uses the public JSON API (no OAuth). See :doc:`docs/trade_deeplinks.md`.
"""

from __future__ import annotations

import json
import math
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
_MAX_FETCH_IDS = 80
_MAX_SCAN_IDS = 80


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
        # PoE2: mirror trades near thousands of divines; ex-based ex*8000 is far too low.
        "mirror": max(cdiv * 9000.0, cex * 8000.0),
        "hinekoras-lock": cex * 5.0,
    }


def normalize_trade_chaos_map(
    chaos_per_name: dict[str, float], settings: Settings
) -> dict[str, float]:
    """Align GGG compact trade currency ids with poe.ninja display-name keys.

    PoE2 trade listings use ``currency: "divine"`` while poe.ninja supplies
    ``"divine orb"`` chaos values. Merging maps without syncing leaves ``divine``
    on the static fallback (often 250) while the UI shows ~26 chaos/div — inflating
    estimates by ~10×.
    """
    m = dict(chaos_per_name)
    cdiv = m.get("divine orb") or m.get("divine")
    cex = m.get("exalted orb") or m.get("exalted")
    if cdiv is not None and float(cdiv) > 0:
        cdiv_f = float(cdiv)
        m["divine"] = cdiv_f
        m["divine orb"] = cdiv_f
    if cex is not None and float(cex) > 0:
        cex_f = float(cex)
        m["exalted"] = cex_f
        m["exalted orb"] = cex_f
    cdiv_eff = m.get("divine") or float(settings.trade_listing_divine_to_chaos)
    cex_eff = max(float(m.get("exalted") or settings.trade_listing_exalt_to_chaos), 1e-6)
    m["mirror"] = max(float(cdiv_eff) * 9000.0, cex_eff * 8000.0)
    return m


def median_chaos(values: list[float]) -> float:
    s = sorted(values)
    n = len(s)
    if n == 0:
        return 0.0
    m = n // 2
    if n % 2:
        return s[m]
    return (s[m - 1] + s[m]) / 2.0


def median_chaos_robust(values: list[float]) -> float:
    """Median with upper-tail resistance (Tukey-style fence on high asks).

    Very expensive outliers (e.g. mirror-priced rows mixed with normal buyouts)
    are excluded only when they sit clearly above an IQR-derived ceiling, so the
    bulk of the market still drives the estimate.
    """
    s = sorted(v for v in values if v > 0 and math.isfinite(v))
    n = len(s)
    if n == 0:
        return 0.0
    if n <= 2:
        return median_chaos(s)
    if n >= 8:
        p90_idx = min(n - 1, int(math.ceil(0.9 * (n - 1))))
        p90 = s[p90_idx]
        trimmed = [x for x in s if x <= p90]
        if len(trimmed) >= max(2, (n + 1) // 2):
            s = trimmed
            n = len(s)
    lo_i = (n - 1) // 4
    hi_i = max(0, (3 * (n - 1)) // 4)
    q1, q3 = s[lo_i], s[hi_i]
    if q1 > q3:
        q1, q3 = q3, q1
    iqr = max(q3 - q1, max(q3, 1e-9) * 1e-6)
    upper = q3 + 3.0 * iqr
    kept = [x for x in s if x <= upper]
    if len(kept) < max(2, (n + 1) // 2):
        kept = s
    return median_chaos(kept)


def _is_mirror_currency(currency: str) -> bool:
    c = (currency or "").lower().strip()
    return c == "mirror" or "mirror" in c


def listing_price_currency(entry: dict[str, Any]) -> str:
    """Return GGG ``listing.price.currency`` (or ``type`` fallback) for a fetch row."""
    li = entry.get("listing")
    if not isinstance(li, dict):
        return ""
    price = li.get("price")
    if not isinstance(price, dict):
        return ""
    return str(price.get("currency") or price.get("type") or "")


def listing_is_mirror_currency(entry: dict[str, Any]) -> bool:
    return _is_mirror_currency(listing_price_currency(entry))


def _divine_chaos_rate(chaos_per_name: dict[str, float], settings: Settings) -> float:
    cdiv = chaos_per_name.get("divine orb") or chaos_per_name.get("divine")
    if cdiv and cdiv > 0:
        return float(cdiv)
    return float(settings.trade_listing_divine_to_chaos)


def estimate_upper_chaos_ceiling(
    chaos_values: list[float],
    chaos_per_name: dict[str, float],
    settings: Settings,
) -> float:
    """Upper bound for listing chaos equivalents used in tier C medians."""
    if not chaos_values:
        return float("inf")
    s = sorted(chaos_values)
    n = len(s)
    p75_idx = max(0, (3 * (n - 1)) // 4)
    p75 = s[p75_idx]
    dynamic_cap = p75 * 4.0 if n >= 4 else float("inf")
    mirror = chaos_per_name.get("mirror") or 0.0
    cdiv = _divine_chaos_rate(chaos_per_name, settings)
    max_div = float(settings.trade_estimate_max_divine_equiv)
    if max_div > 0:
        config_cap = max_div * cdiv
    elif mirror > 0:
        config_cap = mirror * 0.85
    else:
        config_cap = float("inf")
    return min(config_cap, dynamic_cap)


def filter_listing_chaos_samples(
    samples: list[tuple[float, bool]],
    chaos_per_name: dict[str, float],
    settings: Settings,
) -> list[float]:
    """Drop mirror-currency rows and ultra-high chaos asks before median."""
    kept = samples
    if settings.trade_estimate_exclude_mirror_currency:
        kept = [(c, m) for c, m in kept if not m]
    chaos_values = [c for c, _ in kept if c > 0 and math.isfinite(c)]
    if not chaos_values:
        return []
    ceiling = estimate_upper_chaos_ceiling(chaos_values, chaos_per_name, settings)
    return [c for c in chaos_values if c <= ceiling]


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


def listing_chaos_sample(
    entry: dict[str, Any], chaos_per_name: dict[str, float]
) -> tuple[float, bool] | None:
    """Chaos equivalent and mirror-currency flag for median filtering."""
    v = listing_chaos_value(entry, chaos_per_name)
    if v is None or v <= 0:
        return None
    return v, listing_is_mirror_currency(entry)


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
    for _page in range(max_pages):
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
    min_samples: int = 3,
    cap_ids: int = 32,
    redis: Redis | None = None,
    list_ids: list[str] | None = None,
    robust_median: bool = True,
) -> tuple[float, int, bool]:
    """Batched fetches; return ``(median, sample_count, rate_limited)``.

    When *list_ids* is set (caller already ran list pagination), skip the
    duplicate list GET — same policy bucket as search POST / fetch.

    Scans up to *_MAX_SCAN_IDS* listing ids (not only the first GGG ``price asc``
    page — that order is not chaos-normalized, so ``1 mirror`` can rank before
    divines). Applies mirror / ceiling filters, then a robust median on the
    chaos-sorted comparable set.
    """
    chaos_per_name = normalize_trade_chaos_map(chaos_per_name, settings)
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
    med_fn = median_chaos_robust if robust_median else median_chaos
    scan_cap = min(len(ids), max(cap_ids, _MAX_SCAN_IDS), _MAX_FETCH_IDS)
    all_filtered: list[float] = []
    for off in range(0, scan_cap, _FETCH_BATCH):
        chunk = ids[off : off + _FETCH_BATCH]
        rows, fetch_rl = await trade_fetch_listings(
            settings, league, search_id, chunk, redis=redis
        )
        if fetch_rl:
            return 0.0, 0, True
        batch_samples: list[tuple[float, bool]] = []
        for row in rows:
            sample = listing_chaos_sample(row, chaos_per_name)
            if sample is not None:
                batch_samples.append(sample)
        all_filtered.extend(filter_listing_chaos_samples(batch_samples, chaos_per_name, settings))
        if len(all_filtered) >= max(min_samples, cap_ids):
            break
    if len(all_filtered) < min_samples:
        return 0.0, len(all_filtered), False
    all_filtered.sort()
    return med_fn(all_filtered), len(all_filtered), False
