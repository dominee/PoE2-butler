"""Normalize Hideout Butler trade payloads into bodies accepted by GGG's PoE2 trade API."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


def ggg_search_body_from_result_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Return ``{query, sort}`` suitable for ``POST …/api/trade2/search/{league}``.

    Strips app-only keys (``mode``, ``tolerance_pct``) and removes internal stat
    metadata (``bucket``, ``text``, ``template``) from each stat filter, keeping
    fields GGG expects (``id``, ``value``, ``disabled``).
    """
    q = deepcopy(payload.get("query") or {})
    q.pop("mode", None)
    q.pop("tolerance_pct", None)

    stats = q.get("stats")
    if isinstance(stats, list):
        new_stats: list[dict[str, Any]] = []
        for block in stats:
            if not isinstance(block, dict):
                continue
            filt_in = block.get("filters")
            if not isinstance(filt_in, list):
                new_stats.append(block)
                continue
            cleaned: list[dict[str, Any]] = []
            for f in filt_in:
                if not isinstance(f, dict):
                    continue
                if "id" not in f:
                    continue
                row: dict[str, Any] = {"id": f["id"]}
                if "value" in f and isinstance(f["value"], dict):
                    row["value"] = dict(f["value"])
                if "disabled" in f:
                    row["disabled"] = f["disabled"]
                cleaned.append(row)
            nb = {**block, "filters": cleaned}
            new_stats.append(nb)
        q["stats"] = new_stats

    sort = payload.get("sort") if isinstance(payload.get("sort"), dict) else {"price": "asc"}
    return {"query": q, "sort": sort}
