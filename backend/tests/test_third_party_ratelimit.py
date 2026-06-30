"""GGG trade throttle helpers."""

from __future__ import annotations

import asyncio

import pytest
from fakeredis.aioredis import FakeRedis

from app.config import Settings
from app.services.third_party_ratelimit import (
    KEY_PRICE_ESTIMATE_SLOT_PREFIX,
    await_price_estimate_slot,
    parse_retry_after_header,
    release_price_estimate_slot,
)


def test_parse_retry_after_header() -> None:
    assert parse_retry_after_header("60") == 60
    assert parse_retry_after_header("  120  ") == 120
    assert parse_retry_after_header(None) is None
    assert parse_retry_after_header("") is None
    assert parse_retry_after_header("not-a-number") is None


@pytest.mark.asyncio
async def test_price_estimate_slot_serializes_when_limit_one() -> None:
    redis = FakeRedis(decode_responses=True)
    settings = Settings(pricing_max_concurrent_estimates=1)
    t1 = await await_price_estimate_slot(redis, settings)
    assert t1.startswith(KEY_PRICE_ESTIMATE_SLOT_PREFIX)

    acquired_second = asyncio.Event()

    async def try_second() -> None:
        t2 = await await_price_estimate_slot(redis, settings)
        acquired_second.set()
        await release_price_estimate_slot(redis, t2)

    task = asyncio.create_task(try_second())
    await asyncio.sleep(0.05)
    assert not acquired_second.is_set()

    await release_price_estimate_slot(redis, t1)
    await asyncio.wait_for(acquired_second.wait(), timeout=2.0)
    await task
