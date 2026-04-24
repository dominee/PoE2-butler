"""Bundled flavour + per-mod community roll ranges for specific uniques."""

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


def _normalize_hints(raw: Any) -> list[dict[str, str]]:
    if not isinstance(raw, list):
        return []
    out: list[dict[str, str]] = []
    for h in raw:
        if not isinstance(h, dict):
            continue
        w = str(h.get("when_contains", "")).strip()
        r = str(h.get("range", "")).strip()
        if w and r:
            out.append({"when_contains": w, "range": r})
    return out


def lookup_unique_reference(*, name: str, base_type: str) -> dict[str, Any] | None:
    """Return ``flavour`` and/or ``mod_range_hints`` when this unique is documented."""
    n = (name or "").strip()
    b = (base_type or "").strip()
    if not n or not b:
        return None
    n_l, b_l = n.lower(), b.lower()
    for e in _load():
        en = str(e.get("name", "")).strip().lower()
        eb = str(e.get("base_type", "")).strip().lower()
        if n_l == en and b_l == eb:
            out: dict[str, Any] = {}
            if isinstance(e.get("flavour"), str) and e["flavour"].strip():
                out["flavour"] = e["flavour"].strip()
            hints = _normalize_hints(e.get("mod_range_hints"))
            if hints:
                out["mod_range_hints"] = hints
            return out or None
    return None
