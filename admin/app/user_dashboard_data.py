"""Assemble Users dashboard payloads (stats + time series for charts)."""

from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime, timedelta
from typing import Any

from admin.app.dashboard_data import snapshot_mix_bars
from admin.app.db import (
    character_history_by_day,
    price_estimates_by_day,
    shares_created_by_day,
    user_headline_stats,
    user_login_distinct_by_day,
    user_refresh_distinct_by_day,
    user_refresh_events_by_day,
    user_signups_by_day,
    users_before_window,
    users_by_league,
)


def fill_missing_days(
    rows: list[dict[str, Any]],
    days: int,
    *,
    value_key: str = "n",
) -> list[dict[str, Any]]:
    """Ensure a continuous UTC date axis with zeros for quiet days."""
    by_day: dict[date, int] = {}
    for row in rows:
        raw = row.get("day")
        if isinstance(raw, date):
            d = raw
        elif hasattr(raw, "date"):
            d = raw.date()  # type: ignore[union-attr]
        else:
            d = date.fromisoformat(str(raw)[:10])
        by_day[d] = int(row.get(value_key) or 0)

    end = datetime.now(UTC).date()
    start = end - timedelta(days=max(0, days - 1))
    out: list[dict[str, Any]] = []
    d = start
    while d <= end:
        out.append({"day": d.isoformat(), value_key: by_day.get(d, 0)})
        d += timedelta(days=1)
    return out


def cumulative_from_signups(
    signups: list[dict[str, Any]],
    *,
    baseline: int,
    value_key: str = "n",
) -> list[dict[str, Any]]:
    total = baseline
    out: list[dict[str, Any]] = []
    for row in signups:
        total += int(row.get(value_key) or 0)
        out.append({"day": row["day"], "n": total})
    return out


def league_mix_bars(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    total = sum(int(r.get("n") or 0) for r in rows)
    return snapshot_mix_bars(
        [{"kind": r.get("league"), "n": r.get("n")} for r in rows],
        total,
    )


def user_chart_payload(bundle: dict[str, Any]) -> dict[str, Any]:
    """Chart.js series only (embedded in users.html)."""
    keys = (
        "signups_by_day",
        "cumulative_users",
        "refresh_users_by_day",
        "refresh_events_by_day",
        "login_users_by_day",
        "gear_history_by_day",
        "price_estimates_by_day",
        "shares_by_day",
    )
    return {k: bundle.get(k, []) for k in keys}


async def load_user_dashboard_bundle(*, days: int = 90) -> dict[str, Any]:
    window = max(7, min(int(days), 365))
    (
        headline,
        signups_raw,
        baseline,
        refresh_users_raw,
        refresh_events_raw,
        login_users_raw,
        gear_history_raw,
        price_raw,
        shares_raw,
        leagues,
    ) = await asyncio.gather(
        user_headline_stats(),
        user_signups_by_day(window),
        users_before_window(window),
        user_refresh_distinct_by_day(window),
        user_refresh_events_by_day(window),
        user_login_distinct_by_day(window),
        character_history_by_day(window),
        price_estimates_by_day(window),
        shares_created_by_day(window),
        users_by_league(),
    )

    signups = fill_missing_days(signups_raw, window)
    cumulative = cumulative_from_signups(signups, baseline=baseline)
    refresh_users = fill_missing_days(refresh_users_raw, window)
    refresh_events = fill_missing_days(refresh_events_raw, window)
    login_users = fill_missing_days(login_users_raw, window)
    gear_history = fill_missing_days(gear_history_raw, window)
    price_estimates = fill_missing_days(price_raw, window)
    shares = fill_missing_days(shares_raw, window)

    return {
        "days": window,
        "headline": headline,
        "signups_by_day": signups,
        "cumulative_users": cumulative,
        "refresh_users_by_day": refresh_users,
        "refresh_events_by_day": refresh_events,
        "login_users_by_day": login_users,
        "gear_history_by_day": gear_history,
        "price_estimates_by_day": price_estimates,
        "shares_by_day": shares,
        "users_by_league": leagues,
        "league_mix": league_mix_bars(leagues),
    }


def user_bundle_for_json(bundle: dict[str, Any]) -> dict[str, Any]:
    """JSON-serializable copy for /admin/api/users/stats."""
    return dict(bundle)
