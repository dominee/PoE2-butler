"""Mod range database service.

Loads ``backend/app/data/mod_ranges.json`` once at startup (LRU-cached) and
exposes helpers for querying T1 min/max values and full tier lists.

The database has three sections:

- ``stat_hashes`` — keyed by GGG ``magnitude.hash``; populated by
  ``backend/scripts/extract_mod_ranges.py``.  Used for hash-based T1 lookup.

- ``mod_names`` — keyed by GGG mod display name (e.g. ``"of the Volcano"``);
  populated by ``backend/scripts/ingest_repoe_mods.py``.  Bridge for items
  where the hash is not in ``stat_hashes`` yet.

- ``mod_groups`` — keyed by mod family (e.g. ``"FireResistance"``); all tiers
  T1-first.  Used to expose the full tier list and item-level requirements.

When the DB is empty (as shipped), all lookups return ``None``/``[]`` and the
UI degrades gracefully to within-tier roll quality only.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

_DB_PATH = Path(__file__).parents[1] / "data" / "mod_ranges.json"


@lru_cache(maxsize=1)
def _load_full() -> dict:
    """Load and cache the entire mod_ranges.json dict."""
    if not _DB_PATH.exists():
        return {}
    try:
        return json.loads(_DB_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


# ── hash-based lookups (existing API, unchanged) ─────────────────────────────

def get_t1_max(stat_hash: str) -> float | None:
    """Return the T1 maximum value for *stat_hash*, or ``None`` if unknown."""
    entry = (_load_full().get("stat_hashes") or {}).get(stat_hash)
    if not entry:
        return None
    tiers = entry.get("tiers") or []
    t1 = next((t for t in tiers if t.get("tier") == 1), None)
    if not t1:
        return None
    return t1.get("max")


def get_tier_range(stat_hash: str, tier: int) -> tuple[float, float] | None:
    """Return ``(min, max)`` for a specific tier by hash, or ``None`` if unknown."""
    entry = (_load_full().get("stat_hashes") or {}).get(stat_hash)
    if not entry:
        return None
    tiers = entry.get("tiers") or []
    match = next((t for t in tiers if t.get("tier") == tier), None)
    if not match:
        return None
    return (match.get("min"), match.get("max"))


# ── name-based lookups (RePoE bridge) ─────────────────────────────────────────

def get_tiers_for_mod_name(name: str) -> list[dict]:
    """Return all tiers (T1-first) for the mod group that contains *name*.

    Each entry: ``{"tier_ggg": int, "required_level": int, "name": str,
    "stats": [{"id": str, "min": num, "max": num}]}``.
    Returns ``[]`` when *name* is unknown or the DB is unpopulated.
    """
    if not name:
        return []
    mod_names = _load_full().get("mod_names") or {}
    entry = mod_names.get(name)
    if not entry:
        return []
    group = entry.get("group", "")
    if not group:
        return []
    return (_load_full().get("mod_groups") or {}).get(group) or []


def get_t1_max_by_name(name: str) -> float | None:
    """Convenience: T1 max of the primary stat for the mod named *name*.

    Falls back to ``None`` when the name is unknown.  Use this when
    ``get_t1_max(stat_hash)`` returns ``None`` (hash not yet in the DB).
    """
    tiers = get_tiers_for_mod_name(name)
    if not tiers:
        return None
    # tiers is T1-first; first entry is T1.
    t1 = tiers[0]
    stats = t1.get("stats") or []
    if not stats:
        return None
    return stats[0].get("max")


# ── group-based lookups ───────────────────────────────────────────────────────

def get_tiers_for_group(group: str) -> list[dict]:
    """Return all tiers (T1-first) for a mod *group* name.

    Useful when you know the mod family and want to list all tiers.
    """
    return (_load_full().get("mod_groups") or {}).get(group) or []


# ── text-inference helper ─────────────────────────────────────────────────────

# Plain-English words found in mod text that don't appear verbatim as
# GGG implicit_tag keys but can be mapped to existing tags.
_KW_TO_TAGS: dict[str, list[str]] = {
    # "maximum Energy Shield" → tag energy_shield
    "energy": ["energy_shield"],
    "shield": ["energy_shield"],
    # Attributes → tag attribute
    "intelligence": ["attribute"],
    "strength": ["attribute"],
    "dexterity": ["attribute"],
    # Item-found rarity → tag drop
    "rarity": ["drop"],
    # Spirit (PoE2 resource for skills) → tag resource
    "spirit": ["resource"],
    # Accuracy rating → tag attack
    "accuracy": ["attack"],
    # Stun-threshold / stun reduction → tag defences
    "stun": ["defences"],
    # Projectile skills → tag skill
    "projectile": ["skill"],
    # Spell skills → tag caster / skill
    "spell": ["caster", "skill"],
    # Ignite / burn → tag fire
    "ignite": ["fire"],
    # Onslaught → tag speed
    "onslaught": ["speed"],
}


def find_group_for_mod(
    value: float,
    keywords: list[str],
    *,
    is_percent: bool = False,
    ilvl: int = 100,
) -> tuple[str, list[dict]] | None:
    """Find the best-matching mod group for a plain-text mod value.

    Used when GGG ``extended.mods`` is absent (character API items).  Matches
    are found by intersecting ``tag_index`` entries for each keyword, then
    checking which candidate group has a tier whose stat range contains
    *value*.  The tier with the best (lowest) tier_ggg number whose
    ``required_level`` ≤ *ilvl* is selected.

    Args:
        value:      Primary numeric value parsed from the mod text.
        keywords:   Lowercase words extracted from the mod text (stop-words
                    removed) that correspond to GGG ``implicit_tag`` names.
        is_percent: True when the mod text has ``%`` after the number (used to
                    prefer groups whose primary stat_id ends with ``_%`` or
                    ``+%``).
        ilvl:       Item level; used to filter out tiers the item cannot roll.

    Returns:
        ``(group_name, all_tiers_T1_first)`` or ``None`` when no match.
    """
    db = _load_full()
    tag_index: dict[str, list[str]] = db.get("tag_index") or {}
    mod_groups: dict[str, list[dict]] = db.get("mod_groups") or {}

    if not keywords or not mod_groups:
        return None

    def _groups_for_kw(kw: str) -> set[str]:
        """Resolve one keyword to a set of candidate group names, using aliases."""
        direct = set(tag_index.get(kw) or [])
        for alias_tag in _KW_TO_TAGS.get(kw) or []:
            direct |= set(tag_index.get(alias_tag) or [])
        return direct

    # Intersect candidate groups from each keyword.
    candidates: set[str] | None = None
    for kw in keywords:
        groups_for_kw = _groups_for_kw(kw)
        if not groups_for_kw:
            continue
        candidates = groups_for_kw if candidates is None else candidates & groups_for_kw

    # Fallback: union if intersection is empty (avoids missing edge cases).
    if not candidates:
        for kw in keywords:
            groups_for_kw = _groups_for_kw(kw)
            if candidates is None:
                candidates = groups_for_kw
            else:
                candidates |= groups_for_kw

    if not candidates:
        return None

    best_group: str | None = None
    best_tier_num = 999
    # Fallback when value exceeds T1 max (quality-boosted or capped roll).
    overroll_group: str | None = None
    overroll_t1_gap = float("inf")  # closest T1 max relative overshoot

    for group_name in candidates:
        tiers = mod_groups.get(group_name) or []
        for tier in tiers:
            req_level = tier.get("required_level") or 0
            if req_level > ilvl:
                continue
            stats = tier.get("stats") or []
            if not stats:
                continue
            primary = stats[0]
            stat_id: str = primary.get("id") or ""
            # Filter by flat-vs-percent nature of the stat.
            stat_is_pct = stat_id.endswith("+%") or stat_id.endswith("_%") or "_+%_" in stat_id
            if is_percent and not stat_is_pct:
                continue
            if not is_percent and stat_is_pct:
                continue
            mn: float | None = primary.get("min")
            mx: float | None = primary.get("max")
            if mn is None or mx is None:
                continue
            if mn <= value <= mx:
                tier_num: int = tier.get("tier_ggg") or 999
                if tier_num < best_tier_num:
                    best_tier_num = tier_num
                    best_group = group_name
                break  # tiers are sorted, first match within this group is best
            # Track overroll candidate: value > T1 max of this group.
            if tier.get("tier_ggg") == 1 and mx is not None and mx > 0 and value > mx:
                # Ratio value/mx; closer to 1.0 = least overshoot = best match.
                gap = value / mx
                if gap < overroll_t1_gap:
                    overroll_t1_gap = gap
                    overroll_group = group_name

    if best_group is None:
        # Fall back to the group whose T1 max is closest to the observed value
        # (handles items boosted above T1 by quality / crafting).
        best_group = overroll_group

    if best_group is None:
        return None
    tiers_out = mod_groups.get(best_group) or []
    return (best_group, tiers_out)
