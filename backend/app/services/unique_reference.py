"""Bundled flavour + community stat-bound notes for specific uniques.

Used when the GGG payload omits ``flavourText`` (common in some snapshots) or when
per-mod GGG ``magnitudes`` reflect an instance’s roll rather than the item type’s
possible range — the app surface makes that distinction in the UI."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

_PATH = Path(__file__).resolve().parents[1] / "data" / "unique_reference.json"


@lru_cache(maxsize=1)
def _load() -> list[dict[str, Any]]:
    if not _PATH.is_file():
        return []
    try:
        data = json.loads(_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return []
    entries = data.get("entries")
    return [e for e in entries if isinstance(e, dict)] if isinstance(entries, list) else []


def lookup_unique_reference(*, name: str, base_type: str) -> dict[str, str] | None:
    """Return ``flavour`` and/or ``stat_bounds`` when this unique is documented."""
    n = (name or "").strip()
    b = (base_type or "").strip()
    if not n or not b:
        return None
    n_l, b_l = n.lower(), b.lower()
    for e in _load():
        en = str(e.get("name", "")).strip().lower()
        eb = str(e.get("base_type", "")).strip().lower()
        if n_l == en and b_l == eb:
            out: dict[str, str] = {}
            if isinstance(e.get("flavour"), str) and e["flavour"].strip():
                out["flavour"] = e["flavour"].strip()
            if isinstance(e.get("stat_bounds"), str) and e["stat_bounds"].strip():
                out["stat_bounds"] = e["stat_bounds"].strip()
            return out or None
    return None
