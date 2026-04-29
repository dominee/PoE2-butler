"""Redis / arq observability helpers."""

from __future__ import annotations

import pickle

import pytest
from fakeredis.aioredis import FakeRedis

from admin.app import redis_stats as rs


@pytest.fixture(autouse=True)
def clear_redis_caches() -> None:
    rs.get_redis.cache_clear()
    rs.get_redis_raw.cache_clear()
    yield
    rs.get_redis.cache_clear()
    rs.get_redis_raw.cache_clear()


@pytest.mark.asyncio
async def test_queue_summary_counts_in_progress_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeRedis(decode_responses=True)
    await fake.zadd(rs.ARQ_QUEUE_ZSET, {"job-a": 1.0})
    await fake.set(f"{rs.ARQ_IN_PROGRESS_PREFIX}x1", "1", px=120_000)
    await fake.set(f"{rs.ARQ_IN_PROGRESS_PREFIX}x2", "1", px=120_000)

    monkeypatch.setattr(rs, "get_redis", lambda: fake)

    q = await rs.queue_summary()
    assert q["queued"] == 1
    assert q["in_progress"] == 2


@pytest.mark.asyncio
async def test_arq_job_function_breakdown_in_progress_scan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = FakeRedis(decode_responses=False)
    jid = b"abc-uuid-here"
    blob = pickle.dumps({"f": "price_estimate_item", "a": ()})
    await fake.set(rs.ARQ_JOB_KEY_PREFIX.encode() + jid, blob)
    await fake.set(rs.ARQ_IN_PROGRESS_PREFIX.encode() + jid, b"1", px=120_000)
    await fake.zadd(rs.ARQ_QUEUE_ZSET.encode(), {jid: 1.0})

    monkeypatch.setattr(rs, "get_redis_raw", lambda: fake)

    out = await rs.arq_job_function_breakdown(max_queued=10, max_in_progress=10)
    assert out["in_progress_by_function"].get("price_estimate_item") == 1
    assert out["unpickle_failed_in_progress"] == 0
    assert out["queued_by_function"].get("price_estimate_item") == 1
