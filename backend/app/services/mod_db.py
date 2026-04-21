"""Mod range database service.

Loads ``backend/app/data/mod_ranges.json`` once at startup and exposes helpers
for querying T1 min/max values for stat hashes.

The database is populated by running:

    python backend/scripts/extract_mod_ranges.py

which reads poe.ninja exports or real GGG API snapshots that include the
``extended`` field (``/account/characters/{name}?extended=true``).

When the DB is empty (as shipped), all lookups return ``None`` and the UI
gracefully degrades to showing only within-tier roll quality.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

_DB_PATH = Path(__file__).parents[1] / "data" / "mod_ranges.json"


@lru_cache(maxsize=1)
def _load() -> dict:
    if not _DB_PATH.exists():
        return {}
    try:
        raw = json.loads(_DB_PATH.read_text(encoding="utf-8"))
        return raw.get("stat_hashes") or {}
    except Exception:
        return {}


def get_t1_max(stat_hash: str) -> float | None:
    """Return the T1 maximum value for *stat_hash*, or ``None`` if unknown."""
    entry = _load().get(stat_hash)
    if not entry:
        return None
    tiers = entry.get("tiers") or []
    t1 = next((t for t in tiers if t.get("tier") == 1), None)
    if not t1:
        return None
    return t1.get("max")


def get_tier_range(stat_hash: str, tier: int) -> tuple[float, float] | None:
    """Return (min, max) for a specific tier, or ``None`` if unknown."""
    entry = _load().get(stat_hash)
    if not entry:
        return None
    tiers = entry.get("tiers") or []
    match = next((t for t in tiers if t.get("tier") == tier), None)
    if not match:
        return None
    return (match.get("min"), match.get("max"))
