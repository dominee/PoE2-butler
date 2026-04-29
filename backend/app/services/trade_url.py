"""Trade search payload and URL builders.

Two flows are supported, each a pure function over a normalized :class:`Item`:

* :func:`build_exact_search` — "find the same item" with a configurable stat
  tolerance (default ``10%``). Each numeric mod becomes a filter with
  ``min = floor(value * (1 - t))`` and ``max = ceil(value * (1 + t))``.
* :func:`build_upgrade_search` — "find an upgrade" per the spec: each numeric
  mod becomes a filter with ``min = floor(value * 0.95)`` and no upper bound.

Stat text mapping uses a small bundled template→hash map plus optional Redis
catalogue (see :mod:`app.services.trade_stat_catalog`). Filters keep human
``text`` / ``template`` for the clipboard payload; GGG POST bodies use only
``id`` + ``value`` (see :func:`app.services.trade_ggg_body.ggg_search_body_from_result_payload`).
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

from app.domain.item import Item, strip_item_mod_text
from app.services.trade_stat_catalog import bundled_trade_stat_id

TRADE_BASE = "https://www.pathofexile.com/trade2/search/poe2"


# Only values accepted by ``type_filters.filters.rarity.option`` on PoE2 trade.
# Currency / gems / div cards are not rarity filters (GGG returns ``Unknown rarity type``).
RARITY_TO_TRADE_OPTION: dict[str, str | None] = {
    "Normal": "normal",
    "Magic": "magic",
    "Rare": "rare",
    "Unique": "unique",
    "Currency": None,
    "Gem": None,
    "DivinationCard": None,
    "QuestItem": None,
}


@dataclass(frozen=True)
class ParsedMod:
    """A single stat extracted from a mod text line.

    ``template`` replaces each numeric value with ``#`` so that text can later
    be matched against the GGG stat id catalogue.  ``values`` captures the
    numeric parts (either as a single number or a low/high pair).
    """

    text: str
    template: str
    values: list[float]
    is_percent: bool


_NUMBER_RE = re.compile(r"[+-]?\d+(?:\.\d+)?")


def parse_mod_line(text: str) -> ParsedMod:
    """Extract numeric values from a mod line."""
    text = strip_item_mod_text(text)
    matches = _NUMBER_RE.findall(text)
    values = [float(m) for m in matches]
    template = _NUMBER_RE.sub("#", text)
    is_percent = "%" in text
    return ParsedMod(text=text, template=template, values=values, is_percent=is_percent)


_FP_EPS = 1e-9


def _window(value: float, tolerance_pct: float) -> tuple[float, float]:
    """Symmetric ±N% window around ``value``.

    Returns ``(lo, hi)`` with ``lo <= hi`` even when ``value`` is negative.
    """
    t = tolerance_pct / 100.0
    a = value * (1.0 - t)
    b = value * (1.0 + t)
    return (a, b) if a <= b else (b, a)


def _floor_int(value: float) -> int:
    # Guard against floating-point drift like 110.00000000000001 -> ceil -> 111.
    return int(math.floor(value + _FP_EPS))


def _ceil_int(value: float) -> int:
    return int(math.ceil(value - _FP_EPS))


def _bucketize(item: Item) -> list[tuple[str, str]]:
    """Return (bucket, text) pairs for every numeric mod carried by the item."""
    pairs: list[tuple[str, str]] = []
    for mod in item.implicit_mods:
        pairs.append(("implicit", mod))
    for mod in item.explicit_mods:
        pairs.append(("explicit", mod))
    for mod in item.rune_mods:
        pairs.append(("rune", mod))
    for mod in item.enchant_mods:
        pairs.append(("enchant", mod))
    for mod in item.crafted_mods:
        pairs.append(("crafted", mod))
    return pairs


def _stat_filters_for_exact(
    pairs: list[tuple[str, str]], tolerance_pct: float
) -> list[dict[str, Any]]:
    filters: list[dict[str, Any]] = []
    for bucket, text in pairs:
        parsed = parse_mod_line(text)
        if not parsed.values:
            filters.append({"bucket": bucket, "text": parsed.text, "template": parsed.template})
            continue
        # Many mods carry two numbers (e.g. "Adds 18 to 32 Physical Damage").
        # For those we use the *average* as the baseline: a user usually
        # wants similar rolls, not two independent windows.
        baseline = sum(parsed.values) / len(parsed.values)
        lo, hi = _window(baseline, tolerance_pct)
        row: dict[str, Any] = {
            "bucket": bucket,
            "text": parsed.text,
            "template": parsed.template,
            "value": {"min": _floor_int(lo), "max": _ceil_int(hi)},
        }
        sid = bundled_trade_stat_id(bucket, parsed.template)
        if sid:
            row["id"] = sid
        filters.append(row)
    return filters


def _stat_filters_for_upgrade(pairs: list[tuple[str, str]]) -> list[dict[str, Any]]:
    filters: list[dict[str, Any]] = []
    for bucket, text in pairs:
        parsed = parse_mod_line(text)
        if not parsed.values:
            continue  # upgrade only cares about numeric mods
        baseline = sum(parsed.values) / len(parsed.values)
        floor_min = _floor_int(baseline * 0.95)
        row: dict[str, Any] = {
            "bucket": bucket,
            "text": parsed.text,
            "template": parsed.template,
            "value": {"min": floor_min},
        }
        sid = bundled_trade_stat_id(bucket, parsed.template)
        if sid:
            row["id"] = sid
        filters.append(row)
    return filters


def _query_shell(item: Item, stats: list[dict[str, Any]]) -> dict[str, Any]:
    """Build the GGG PoE2 trade query (``query`` + ``sort``).

    PoE2 expects base item name as a plain string in ``query["type"]``, not
    ``type_filters.filters.type`` (that shape is invalid). Rarity uses
    ``filters.type_filters.filters.rarity`` alongside ``type`` when set.

    **Instant Buyout** uses top-level ``query.status.option = "securable"``.
    The filter metadata groups that as ``status_filters`` in
    ``GET /api/trade2/data/filters``, but ``POST …/search`` rejects
    ``query.filters.status_filters`` (``Unknown filter group``).

    We do **not** send ``trade_filters.sale_type`` with JSON ``null`` for
    “Buyout or Fixed Price”: GGG returns ``Invalid sale type``. Securable
    listings are already instant-buyout scope; omitting ``trade_filters`` keeps
    the payload valid.
    """
    query: dict[str, Any] = {"status": {"option": "securable"}}
    if item.base_type:
        query["type"] = item.base_type
    # Uniques are identified by ``name`` + ``type`` (base); ``type`` alone matches every base.
    if item.rarity == "Unique" and item.name.strip():
        query["name"] = item.name.strip()
    filt = query.setdefault("filters", {})
    rarity_option = RARITY_TO_TRADE_OPTION.get(item.rarity)
    if rarity_option:
        tf = filt.setdefault("type_filters", {})
        tf["disabled"] = False
        tf.setdefault("filters", {})["rarity"] = {"option": rarity_option}
    if stats:
        query["stats"] = [{"type": "and", "filters": stats}]
    return {"query": query, "sort": {"price": "asc"}}


def stat_filters_for_exact_item(item: Item, tolerance_pct: float) -> list[dict[str, Any]]:
    """Stat filter rows for an exact search (same rules as :func:`build_exact_search`)."""
    if tolerance_pct < 0:
        raise ValueError("tolerance_pct_must_be_non_negative")
    return _stat_filters_for_exact(_bucketize(item), tolerance_pct)


def build_exact_search_with_stat_filters(
    item: Item,
    stat_filters: list[dict[str, Any]],
    *,
    tolerance_pct: float = 10.0,
    league: str | None = None,
) -> dict[str, Any]:
    """Build exact search payload using a (possibly relaxed) stat filter list."""
    if tolerance_pct < 0:
        raise ValueError("tolerance_pct_must_be_non_negative")
    payload = _query_shell(item, stat_filters)
    payload["mode"] = "exact"
    payload["tolerance_pct"] = tolerance_pct
    return {
        "mode": "exact",
        "league": league or item.inventory_id or "",
        "url": build_trade_url(league or ""),
        "payload": payload,
    }


def build_exact_search(
    item: Item,
    *,
    tolerance_pct: float = 10.0,
    league: str | None = None,
) -> dict[str, Any]:
    """Payload + URL for a "find the same item" trade search.

    ``tolerance_pct`` is the symmetric percentage window around each numeric
    stat. ``0`` collapses the window to the exact value; ``100`` doubles it.
    """
    if tolerance_pct < 0:
        raise ValueError("tolerance_pct_must_be_non_negative")
    stats = stat_filters_for_exact_item(item, tolerance_pct)
    payload = _query_shell(item, stats)
    payload["mode"] = "exact"
    payload["tolerance_pct"] = tolerance_pct
    return {
        "mode": "exact",
        "league": league or item.inventory_id or "",
        "url": build_trade_url(league or ""),
        "payload": payload,
    }


def build_upgrade_search(item: Item, *, league: str | None = None) -> dict[str, Any]:
    """Payload + URL for a "find an upgrade" search.

    Each numeric stat has its lower bound pinned at ``floor(value * 0.95)``
    with no upper bound.  Non-numeric stats are dropped; they cannot anchor
    an upgrade window.
    """
    stats = _stat_filters_for_upgrade(_bucketize(item))
    payload = _query_shell(item, stats)
    payload["mode"] = "upgrade"
    return {
        "mode": "upgrade",
        "league": league or "",
        "url": build_trade_url(league or ""),
        "payload": payload,
    }


def build_trade_url(league: str) -> str:
    """Trade site URL for a league (no search id)."""
    if not league:
        return TRADE_BASE
    return f"{TRADE_BASE}/{quote(league, safe='')}"


def build_trade_url_with_search_id(league: str, search_id: str) -> str:
    """Public trade URL including GGG search id: ``…/poe2/<league>/<id>``."""
    base = build_trade_url(league)
    sid = (search_id or "").strip()
    if not sid:
        return base
    return f"{base}/{sid}"
