"""Users dashboard helpers and API."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import bcrypt
import pytest
from httpx import ASGITransport, AsyncClient

from admin.app.config import get_admin_settings
from admin.app.main import app
from admin.app.user_dashboard_data import (
    cumulative_from_signups,
    fill_missing_days,
    league_mix_bars,
    user_bundle_for_json,
    user_chart_payload,
)


def test_fill_missing_days_zero_fills_gaps() -> None:
    today = datetime.now(UTC).date()
    yesterday = today - timedelta(days=1)
    rows = [{"day": yesterday.isoformat(), "n": 3}]
    filled = fill_missing_days(rows, 3)
    assert len(filled) == 3
    assert filled[0]["n"] == 0
    assert filled[1]["n"] == 3
    assert filled[2]["n"] == 0


def test_cumulative_from_signups() -> None:
    signups = [{"day": "2026-01-01", "n": 2}, {"day": "2026-01-02", "n": 1}]
    out = cumulative_from_signups(signups, baseline=10)
    assert out[0]["n"] == 12
    assert out[1]["n"] == 13


def test_league_mix_bars_percentages() -> None:
    rows = [{"league": "Standard", "n": 25}, {"league": "Hardcore", "n": 75}]
    mix = league_mix_bars(rows)
    assert mix[0]["pct"] == 25.0
    assert mix[1]["pct"] == 75.0


def test_user_chart_payload_strips_headline() -> None:
    bundle = {
        "headline": {"total_users": 9},
        "signups_by_day": [{"day": "2026-01-01", "n": 1}],
        "cumulative_users": [{"day": "2026-01-01", "n": 9}],
    }
    chart = user_chart_payload(bundle)
    assert "headline" not in chart
    assert chart["signups_by_day"][0]["n"] == 1


def test_user_bundle_for_json_is_copy() -> None:
    bundle = {"days": 90, "headline": {"total_users": 1}}
    out = user_bundle_for_json(bundle)
    assert out["headline"]["total_users"] == 1


@pytest.fixture
def admin_password_hash() -> str:
    return bcrypt.hashpw(b"s3cret", bcrypt.gensalt()).decode()


@pytest.mark.asyncio
async def test_users_stats_api_requires_auth() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/admin/api/users/stats")
    assert resp.status_code == 302


@pytest.mark.asyncio
async def test_users_page_includes_chart_assets(
    monkeypatch: pytest.MonkeyPatch,
    admin_password_hash: str,
) -> None:
    get_admin_settings.cache_clear()

    async def fake_bundle(*, days: int = 90):
        return {
            "days": days,
            "headline": {
                "total_users": 1,
                "active_30d": 1,
                "inactive_30d": 0,
                "not_logged_in_30d": 0,
                "never_refreshed": 0,
            },
            "signups_by_day": [{"day": "2026-01-01", "n": 1}],
            "cumulative_users": [{"day": "2026-01-01", "n": 1}],
            "refresh_users_by_day": [],
            "refresh_events_by_day": [],
            "login_users_by_day": [],
            "gear_history_by_day": [],
            "price_estimates_by_day": [],
            "shares_by_day": [],
            "users_by_league": [],
            "league_mix": [],
        }

    async def fake_list_users(*, query: str | None = None):
        return []

    monkeypatch.setenv("ADMIN_PASSWORD_HASH", admin_password_hash)
    monkeypatch.setenv("ADMIN_SESSION_SECRET", "x" * 32)
    monkeypatch.setattr("admin.app.main.load_user_dashboard_bundle", fake_bundle)
    monkeypatch.setattr("admin.app.main.list_users", fake_list_users)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        login = await client.post(
            "/admin/login",
            data={"username": "admin", "password": "s3cret"},
            follow_redirects=False,
        )
        assert login.status_code == 303
        resp = await client.get("/admin/users")
        assert resp.status_code == 200
        body = resp.text
        assert "/static/chart.umd.min.js" in body
        assert "user-chart-data" in body
        assert "Never logged in" not in body


@pytest.mark.asyncio
async def test_users_stats_api_authenticated(
    monkeypatch: pytest.MonkeyPatch,
    admin_password_hash: str,
) -> None:
    get_admin_settings.cache_clear()

    async def fake_bundle(*, days: int = 90):
        return {
            "days": days,
            "headline": {
                "total_users": 5,
                "active_30d": 2,
                "inactive_30d": 3,
                "not_logged_in_30d": 1,
                "never_refreshed": 0,
            },
            "signups_by_day": [],
            "cumulative_users": [],
            "refresh_users_by_day": [],
            "refresh_events_by_day": [],
            "login_users_by_day": [],
            "gear_history_by_day": [],
            "price_estimates_by_day": [],
            "shares_by_day": [],
            "users_by_league": [],
            "league_mix": [],
        }

    monkeypatch.setenv("ADMIN_PASSWORD_HASH", admin_password_hash)
    monkeypatch.setenv("ADMIN_SESSION_SECRET", "x" * 32)
    monkeypatch.setattr("admin.app.main.load_user_dashboard_bundle", fake_bundle)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        login = await client.post(
            "/admin/login",
            data={"username": "admin", "password": "s3cret"},
            follow_redirects=False,
        )
        assert login.status_code == 303

        resp = await client.get("/admin/api/users/stats?days=30")
        assert resp.status_code == 200
        body = resp.json()
        assert body["days"] == 30
        assert body["headline"]["total_users"] == 5
