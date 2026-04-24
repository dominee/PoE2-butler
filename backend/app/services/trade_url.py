"""Trade search payload and URL builders.

Two flows are supported, each a pure function over a normalized :class:`Item`:

* :func:`build_exact_search` — "find the same item" with a configurable stat
  tolerance (default ``10%``). Each numeric mod becomes a filter with
  ``min = floor(value * (1 - t))`` and ``max = ceil(value * (1 + t))``.
* :func:`build_upgrade_search` — "find an upgrade" per the spec: each numeric
  mod becomes a filter with ``min = floor(value * 0.95)`` and no upper bound.

Stat text mapping to GGG trade stat ids requires a static id catalogue that
GGG exposes through their trade API.  That catalogue is out of scope for M2;
until it is loaded, filters carry the mod text verbatim under ``text`` and the
builder marks numeric mods so the frontend can render a useful filter summary
and the future Discord bot can substitute real stat ids when they become
available.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

from app.domain.item import Item
from app.services.trade_stat_catalog import BUNDLED_TEMPLATE_TO_STAT_ID

TRADE_BASE = "https://www.pathofexile.com/trade2/search/poe2"


RARITY_TO_TRADE_OPTION = {
    "Normal": "normal",
    "Magic": "magic",
    "Rare": "rare",
    "Unique": "unique",
    "Currency": "currency",
    "Gem": "gem",
    "DivinationCard": "card",
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
        sid = BUNDLED_TEMPLATE_TO_STAT_ID.get(parsed.template)
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
        sid = BUNDLED_TEMPLATE_TO_STAT_ID.get(parsed.template)
        if sid:
            row["id"] = sid
        filters.append(row)
    return filters


def _type_filters(item: Item) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if item.base_type:
        out["type"] = {"option": item.base_type}
    rarity_option = RARITY_TO_TRADE_OPTION.get(item.rarity)
    if rarity_option and item.rarity != "Unique":
        out["rarity"] = {"option": rarity_option}
    return out


def _query_shell(item: Item, stats: list[dict[str, Any]]) -> dict[str, Any]:
    """Build the GGG trade-API query shell (before stat id substitution)."""
    query: dict[str, Any] = {
        "status": {"option": "online"},
    }
    type_filters = _type_filters(item)
    if type_filters:
        query["filters"] = {"type_filters": {"filters": type_filters}}
    if stats:
        query["stats"] = [{"type": "and", "filters": stats}]
    return {"query": query, "sort": {"price": "asc"}}


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
    stats = _stat_filters_for_exact(_bucketize(item), tolerance_pct)
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
    """Base trade URL for a league.

    Full pre-fill requires POSTing the payload to GGG's trade API and
    redirecting to ``/trade2/search/poe2/<league>/<id>``. Until that is wired
    (it needs an approved OAuth client), the URL returned here opens the
    trade site at the chosen league so the user can paste the payload or
    manually replicate the filters.
    """
    if not league:
        return TRADE_BASE
    return f"{TRADE_BASE}/{quote(league, safe='')}"
