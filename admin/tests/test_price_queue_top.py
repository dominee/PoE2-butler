"""Top queued price estimate jobs (Redis)."""

from __future__ import annotations

import json

import pytest
from fakeredis.aioredis import FakeRedis

from admin.app import redis_stats as rs


@pytest.fixture(autouse=True)
def clear_redis() -> None:
    rs.get_redis.cache_clear()
    yield
    rs.get_redis.cache_clear()


@pytest.mark.asyncio
async def test_top_queued_price_estimate_jobs_orders_running_first(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = FakeRedis(decode_responses=True)
    j1 = {
        "status": "queued",
        "user_id": "u1",
        "item_id": "a",
        "item_name": "Boots",
        "league": "L",
        "updated_at": "2026-01-01T00:00:01",
    }
    j2 = {
        "status": "running",
        "user_id": "u1",
        "item_id": "b",
        "item_name": "Bow",
        "league": "L",
        "updated_at": "2026-01-01T00:00:00",
    }
    await fake.set("poe2b:price_job:111", json.dumps(j1))
    await fake.set("poe2b:price_job:222", json.dumps(j2))
    await fake.set("poe2b:price_job:333", json.dumps({"status": "completed", "user_id": "u1"}))

    monkeypatch.setattr(rs, "get_redis", lambda: fake)
    out = await rs.top_queued_price_estimate_jobs(limit=10)
    assert len(out) == 2
    assert out[0]["status"] == "running"
    assert out[1]["status"] == "queued"


@pytest.mark.asyncio
async def test_price_queue_route_requires_auth() -> None:
    from admin.app.main import app
    from httpx import ASGITransport, AsyncClient

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        r = await client.get("/admin/price-queue")
    assert r.status_code == 302
