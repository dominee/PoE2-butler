"""Dashboard helpers and authenticated API summary."""

from __future__ import annotations

from datetime import UTC, datetime

import bcrypt
import pytest
from httpx import ASGITransport, AsyncClient

from admin.app.config import get_admin_settings
from admin.app.dashboard_data import bundle_for_json, snapshot_mix_bars
from admin.app.main import app
from admin.app.redis_stats import parse_health_body, probe_ok


def test_snapshot_mix_bars_percentages() -> None:
    rows = [{"kind": "profile", "n": 25}, {"kind": "stash_tab", "n": 75}]
    mix = snapshot_mix_bars(rows, 100)
    assert mix[0]["pct"] == 25.0
    assert mix[1]["pct"] == 75.0
    assert snapshot_mix_bars([], 0) == []


def test_snapshot_mix_zero_total() -> None:
    mix = snapshot_mix_bars([{"kind": "x", "n": 5}], 0)
    assert mix[0]["pct"] == 0.0


def test_parse_health_body_extracts_version() -> None:
    body = '{"status":"ok","version":"1.2.3"}'
    p = parse_health_body(200, body)
    assert p["version"] == "1.2.3"
    assert p["status"] == "ok"


def test_parse_health_body_non_json() -> None:
    p = parse_health_body(200, "not json")
    assert p["version"] is None


def test_probe_ok() -> None:
    assert probe_ok({"status_code": 200, "error": None}) is True
    assert probe_ok({"status_code": 503, "error": None}) is False
    assert probe_ok({"status_code": 200, "error": "x"}) is False


def test_bundle_for_json_serializes_datetimes() -> None:
    bundle = {
        "totals": {"users": 1, "snapshots": 2},
        "metrics": {
            "active_users_7d": 1,
            "token_rows": 1,
            "active_shares": 0,
            "snapshots_24h": 2,
            "last_snapshot_at": datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC),
        },
        "metrics_iso": {},
        "snapshots_by_kind": [],
        "snapshot_mix": [],
        "redis": {},
        "price_cache": {"key_count": 0, "sample": []},
        "queue": {"queued": 0, "in_progress": 0},
        "health": {},
        "upstream_ok": True,
    }
    out = bundle_for_json(bundle)
    assert out["metrics"]["last_snapshot_at"].startswith("2026-01-02")


@pytest.fixture
def admin_password_hash() -> str:
    return bcrypt.hashpw(b"s3cret", bcrypt.gensalt()).decode()


@pytest.mark.asyncio
async def test_api_summary_requires_auth() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/admin/api/summary")
    assert r.status_code == 302


@pytest.mark.asyncio
async def test_api_summary_returns_json(
    monkeypatch: pytest.MonkeyPatch,
    admin_password_hash: str,
) -> None:
    get_admin_settings.cache_clear()

    async def fake_bundle() -> dict:
        return {
            "totals": {"users": 3, "snapshots": 10},
            "metrics": {
                "active_users_7d": 1,
                "token_rows": 2,
                "active_shares": 0,
                "snapshots_24h": 4,
                "last_snapshot_at": None,
            },
            "metrics_iso": {
                "active_users_7d": 1,
                "token_rows": 2,
                "active_shares": 0,
                "snapshots_24h": 4,
                "last_snapshot_at": None,
            },
            "snapshots_by_kind": [{"kind": "profile", "n": 10}],
            "snapshot_mix": [{"kind": "profile", "n": 10, "pct": 100.0}],
            "redis": {
                "key_count": 1,
                "used_memory_human": "1M",
                "used_memory_peak_human": "2M",
                "maxmemory_human": None,
                "connected_clients": 2,
                "evicted_keys": 0,
                "expired_keys": 0,
            },
            "price_cache": {"key_count": 0, "sample": []},
            "queue": {"queued": 0, "in_progress": 0},
            "health": {
                "/healthz": {
                    "status_code": 200,
                    "latency_ms": 1.0,
                    "version": "0.0.1",
                    "body_status": "ok",
                    "error": None,
                },
            },
            "upstream_ok": True,
        }

    monkeypatch.setenv("ADMIN_PASSWORD_HASH", admin_password_hash)
    monkeypatch.setenv("ADMIN_SESSION_SECRET", "x" * 32)
    monkeypatch.setattr("admin.app.main.load_dashboard_bundle", fake_bundle)
    get_admin_settings.cache_clear()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        login = await client.post(
            "/admin/login",
            data={"username": "admin", "password": "s3cret"},
            follow_redirects=False,
        )
        assert login.status_code == 303
        assert login.cookies.get("poe2b_admin")
        r = await client.get("/admin/api/summary")
    assert r.status_code == 200
    data = r.json()
    assert data["totals"]["users"] == 3
    assert data["upstream_ok"] is True
    assert data["health"]["/healthz"]["version"] == "0.0.1"
