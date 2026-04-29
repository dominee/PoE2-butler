"""Top queued price estimate jobs (Redis)."""

from __future__ import annotations

import json
import uuid

import bcrypt
import pytest
from fakeredis.aioredis import FakeRedis
from httpx import ASGITransport, AsyncClient

from admin.app import redis_stats as rs
from admin.app.config import get_admin_settings
from admin.app.main import app


@pytest.fixture(autouse=True)
def clear_redis() -> None:
    g = rs.get_redis
    if hasattr(g, "cache_clear"):
        g.cache_clear()
    yield
    g = rs.get_redis
    if hasattr(g, "cache_clear"):
        g.cache_clear()


@pytest.fixture
def admin_password_hash() -> str:
    return bcrypt.hashpw(b"s3cret", bcrypt.gensalt()).decode()


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
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        r = await client.get("/admin/price-queue")
    assert r.status_code == 302


def test_normalize_price_job_id() -> None:
    u = uuid.uuid4()
    assert rs.normalize_price_job_id(str(u)) == str(u)
    assert rs.normalize_price_job_id("  " + str(u).upper() + "  ") == str(u)
    assert rs.normalize_price_job_id("not-a-uuid") is None
    assert rs.normalize_price_job_id("") is None


@pytest.mark.asyncio
async def test_delete_price_job_key(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeRedis(decode_responses=True)
    jid = str(uuid.uuid4())
    await fake.set(
        f"{rs.PRICE_JOB_KEY_PREFIX}{jid}",
        json.dumps({"status": "queued", "user_id": "u"}),
    )
    rs.get_redis.cache_clear()
    monkeypatch.setattr(rs, "get_redis", lambda: fake)
    ok, outcome = await rs.delete_price_job_key(jid)
    assert ok and outcome == "deleted"
    assert await fake.get(f"{rs.PRICE_JOB_KEY_PREFIX}{jid}") is None
    ok2, outcome2 = await rs.delete_price_job_key(jid)
    assert ok2 and outcome2 == "missing"


@pytest.mark.asyncio
async def test_clear_inflight_price_estimate_jobs(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeRedis(decode_responses=True)
    j1, j2, j3 = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
    await fake.set(f"{rs.PRICE_JOB_KEY_PREFIX}{j1}", json.dumps({"status": "queued"}))
    await fake.set(f"{rs.PRICE_JOB_KEY_PREFIX}{j2}", json.dumps({"status": "running"}))
    await fake.set(f"{rs.PRICE_JOB_KEY_PREFIX}{j3}", json.dumps({"status": "completed"}))
    rs.get_redis.cache_clear()
    monkeypatch.setattr(rs, "get_redis", lambda: fake)
    n = await rs.clear_inflight_price_estimate_jobs()
    assert n == 2
    assert await fake.get(f"{rs.PRICE_JOB_KEY_PREFIX}{j1}") is None
    assert await fake.get(f"{rs.PRICE_JOB_KEY_PREFIX}{j2}") is None
    assert await fake.get(f"{rs.PRICE_JOB_KEY_PREFIX}{j3}") is not None


@pytest.mark.asyncio
async def test_price_queue_remove_and_clear_require_auth() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        r1 = await client.post("/admin/price-queue/remove", data={"job_id": str(uuid.uuid4())})
        r2 = await client.post("/admin/price-queue/clear")
    assert r1.status_code == 302
    assert r2.status_code == 302


@pytest.mark.asyncio
async def test_price_queue_remove_redirects_when_authenticated(
    monkeypatch: pytest.MonkeyPatch,
    admin_password_hash: str,
) -> None:
    fake = FakeRedis(decode_responses=True)
    jid = str(uuid.uuid4())
    await fake.set(
        f"{rs.PRICE_JOB_KEY_PREFIX}{jid}",
        json.dumps({"status": "queued", "user_id": "u", "item_id": "i"}),
    )
    rs.get_redis.cache_clear()
    monkeypatch.setattr(rs, "get_redis", lambda: fake)

    get_admin_settings.cache_clear()
    monkeypatch.setenv("ADMIN_PASSWORD_HASH", admin_password_hash)
    monkeypatch.setenv("ADMIN_SESSION_SECRET", "x" * 32)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        login = await client.post(
            "/admin/login",
            data={"username": "admin", "password": "s3cret"},
            follow_redirects=False,
        )
        assert login.status_code == 303
        rem = await client.post(
            "/admin/price-queue/remove",
            data={"job_id": jid},
            follow_redirects=False,
        )
    assert rem.status_code == 303
    assert "notice=removed" in (rem.headers.get("location") or "")
    assert await fake.get(f"{rs.PRICE_JOB_KEY_PREFIX}{jid}") is None
    get_admin_settings.cache_clear()
