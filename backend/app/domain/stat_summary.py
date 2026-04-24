"""Cumulative character stats from equipped :class:`Item` lists (MVP heuristics).

Heuristic regexes only; expand with a proper stat ontology later (INSTRUCTIONS).
"""

from __future__ import annotations

import re
from collections import defaultdict

from app.domain.item import Item, _strip_tags

_LIFE = re.compile(r"\+?(\d+) to maximum (?:Life|Mana)", re.IGNORECASE)
_TRI_RES = re.compile(r"\+?(\d+)% to all Elemental Resistances", re.IGNORECASE)


def _all_mod_texts(item: Item) -> list[str]:
    parts: list[str] = []
    for group in (
        item.implicit_mods,
        item.rune_mods,
        item.explicit_mods,
        item.crafted_mods,
        item.enchant_mods,
    ):
        parts.extend(group)
    for s in item.socketed_items:
        parts.extend(_all_mod_texts(s))
    return [_strip_tags(m) for m in parts if m]


def summarize_equipment(items: list[Item]) -> dict[str, float]:
    """Return aggregated numeric stats (MVP: life, str/dex/int, resists, tri-res)."""
    totals: dict[str, float] = defaultdict(float)
    for it in items:
        for t in _all_mod_texts(it):
            m = _LIFE.search(t)
            if m and "life" in t.lower():
                totals["life"] += float(m.group(1))
            elif m and "mana" in t.lower():
                totals["mana"] += float(m.group(1))
            m2 = re.search(r"\+?(\d+) to (Strength|Dexterity|Intelligence)", t, re.IGNORECASE)
            if m2:
                k = m2.group(2).lower()
                totals[k] += float(m2.group(1))
            m3 = _TRI_RES.search(t)
            if m3:
                v = float(m3.group(1))
                totals["fire_res"] += v
                totals["cold_res"] += v
                totals["lightning_res"] += v
    return dict(totals)
