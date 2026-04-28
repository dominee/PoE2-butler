"""Stat filter relaxation for trade search (same mod ordering as :mod:`trade_url`)."""

from __future__ import annotations

from typing import Any

# Drop order: crafted and enchant are least “structural” for identity; explicit last.
_BUCKET_DROP_ORDER: dict[str, int] = {
    "crafted": 0,
    "enchant": 1,
    "rune": 2,
    "implicit": 3,
    "explicit": 4,
}


def stat_filter_drop_indices(filters: list[dict[str, Any]]) -> list[int]:
    """Indices to remove one-at-a-time. First index removed = first relaxation step.

    Within each bucket, **later** filters (higher list index) are removed first
    (usually less critical for rare identity than earlier rolled mods).
    """
    n = len(filters)
    by_bucket: dict[str, list[int]] = {}
    for i, f in enumerate(filters):
        b = str(f.get("bucket") or "explicit")
        by_bucket.setdefault(b, []).append(i)
    order: list[int] = []
    for b in sorted(_BUCKET_DROP_ORDER, key=lambda k: _BUCKET_DROP_ORDER.get(k, 99)):
        idxs = by_bucket.get(b) or []
        for j in reversed(idxs):
            order.append(j)
    if len(order) != n:
        # include any unknown bucket at the end, later indices first
        rest = [i for i in range(n) if i not in set(order)]
        for j in reversed(rest):
            order.append(j)
    return order


def apply_relaxation_step(
    full_filters: list[dict[str, Any]], step: int, drop_indices: list[int]
) -> list[dict[str, Any]]:
    """``step`` = how many filter rows have been removed (0 = full)."""
    if step <= 0:
        return list(full_filters)
    if step > len(drop_indices):
        return []
    removed = set(drop_indices[:step])
    return [f for i, f in enumerate(full_filters) if i not in removed]
