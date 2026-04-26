"""Assemble dashboard + API summary payloads (read-only aggregates)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from admin.app.db import count_snapshots_by_kind, count_totals, dashboard_metrics
from admin.app.redis_stats import (
    backend_health,
    price_cache_summary,
    probe_ok,
    queue_summary,
    redis_summary,
)


def snapshot_mix_bars(rows: list[dict], total_snapshots: int) -> list[dict[str, Any]]:
    """Turn GROUP BY kind counts into percentage rows for CSS bars."""
    out: list[dict[str, Any]] = []
    total = max(0, int(total_snapshots))
    for row in rows:
        n = int(row.get("n") or 0)
        pct = round((100.0 * n / total), 1) if total else 0.0
        out.append({"kind": row.get("kind"), "n": n, "pct": pct})
    return out


def _dt_iso(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


async def load_dashboard_bundle() -> dict[str, Any]:
    totals = await count_totals()
    metrics = await dashboard_metrics()
    snapshots_by_kind = await count_snapshots_by_kind()
    mix = snapshot_mix_bars(snapshots_by_kind, totals["snapshots"])
    redis = await redis_summary()
    price_cache = await price_cache_summary()
    queue = await queue_summary()
    health = await backend_health()
    upstream_ok = all(probe_ok(v) for v in health.values()) if health else False
    return {
        "totals": totals,
        "metrics": metrics,
        "metrics_iso": {
            **metrics,
            "last_snapshot_at": _dt_iso(metrics.get("last_snapshot_at")),
        },
        "snapshots_by_kind": snapshots_by_kind,
        "snapshot_mix": mix,
        "redis": redis,
        "price_cache": price_cache,
        "queue": queue,
        "health": health,
        "upstream_ok": upstream_ok,
    }


def bundle_for_json(bundle: dict[str, Any]) -> dict[str, Any]:
    """JSON-serializable copy (datetimes as ISO strings)."""
    metrics = dict(bundle["metrics"])
    metrics["last_snapshot_at"] = _dt_iso(metrics.get("last_snapshot_at"))
    return {
        "totals": bundle["totals"],
        "metrics": metrics,
        "snapshots_by_kind": bundle["snapshots_by_kind"],
        "snapshot_mix": bundle["snapshot_mix"],
        "redis": bundle["redis"],
        "price_cache": {
            "key_count": bundle["price_cache"]["key_count"],
            "sample": bundle["price_cache"]["sample"],
        },
        "queue": bundle["queue"],
        "health": bundle["health"],
        "upstream_ok": bundle["upstream_ok"],
    }
