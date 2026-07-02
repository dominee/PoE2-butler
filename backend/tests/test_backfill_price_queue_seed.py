"""Backfill pre-seeds Redis price jobs as ``queued`` so admin can show the batch."""

from __future__ import annotations

import json
import uuid
from typing import Any
from unittest.mock import MagicMock

import pytest
from fakeredis.aioredis import FakeRedis

from app.config import Settings
from app.db import base as db_base
from app.services.pricing.estimate_state import PriceJobState, dedup_key, save_job_state


@pytest.mark.asyncio
async def test_backfill_seeds_all_jobs_queued_before_first_hybrid_starts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.workers import arq_worker as w

    uid = uuid.uuid4()
    fake_redis: Any = FakeRedis(decode_responses=True)

    class FakeExecuteResult:
        def scalar_one_or_none(self) -> None:
            return None

    class FakeSession:
        async def get(self, _model: type, pk: uuid.UUID) -> Any:
            if pk != uid:
                return None
            u = MagicMock()
            u.id = uid
            u.trade_tolerance_pct = 10
            return u

        async def commit(self) -> None:
            return None

        async def rollback(self) -> None:
            return None

        async def execute(self, _stmt: Any) -> FakeExecuteResult:
            return FakeExecuteResult()

        def add(self, _obj: Any) -> None:
            return None

    class FakeCM:
        async def __aenter__(self) -> FakeSession:
            return FakeSession()

        async def __aexit__(self, *_a: object) -> None:
            return None

    class FakeSessionMaker:
        def __call__(self) -> FakeCM:
            return FakeCM()

    raws = [
        ("id1", {"id": "id1", "frameType": 5, "typeLine": "Divine Orb"}),
        ("id2", {"id": "id2", "frameType": 5, "typeLine": "Chaos Orb"}),
        ("id3", {"id": "id3", "frameType": 5, "typeLine": "Exalted Orb"}),
    ]

    async def fake_list_meta(*_a: Any, **_k: Any) -> dict[str, Any]:
        return {}

    async def noop_upsert(*_a: Any, **_k: Any) -> None:
        return None

    async def fake_collect_stash(*_a: Any, **_k: Any) -> list[tuple[str, dict]]:
        return list(raws)

    saw_first_hybrid = False

    async def fake_run_hybrid(
        _settings: Settings,
        redis: Any,
        user_id: str,
        item: Any,
        league: str,
        tol: float,
        *,
        job_id: str,
        price_svc: Any,
    ) -> None:
        nonlocal saw_first_hybrid
        keys = sorted([k async for k in redis.scan_iter(match="poe2b:price_job:*")])
        statuses = []
        for k in keys:
            raw = await redis.get(k)
            if raw:
                statuses.append(json.loads(raw)["status"])
        if not saw_first_hybrid:
            assert statuses == ["queued", "queued", "queued"], statuses
            for iid in ("id1", "id2", "id3"):
                assert await fake_redis.get(dedup_key(str(uid), iid, "TestLeague"))
            saw_first_hybrid = True
        st = PriceJobState(
            user_id=user_id,
            item_id=str(item.id),
            item_name="x",
            league=league,
            status="completed",
            message="test",
        )
        await save_job_state(redis, job_id, st)
        return

    async def noop_throttle(*_a: Any, **_k: Any) -> None:
        return None

    maker = FakeSessionMaker()
    monkeypatch.setattr(db_base, "_session_factory", lambda: maker)
    monkeypatch.setattr(w, "_session_factory", lambda: maker)
    monkeypatch.setattr(w, "upsert_price_job_state", noop_upsert)
    monkeypatch.setattr(
        "app.services.pricing.estimate_persist.list_estimate_meta_for_league",
        fake_list_meta,
    )
    monkeypatch.setattr(w, "_collect_stash_raws", fake_collect_stash)
    monkeypatch.setattr(w, "run_hybrid_price_estimate", fake_run_hybrid)
    monkeypatch.setattr(w, "throttle", noop_throttle)
    monkeypatch.setattr(
        w,
        "Redis",
        type(
            "R",
            (),
            {"from_url": classmethod(lambda cls, *_a, **_k: fake_redis)},
        ),
    )
    monkeypatch.setattr(
        w,
        "get_settings",
        lambda: Settings(redis_url="redis://fake", pricing_source="static"),
    )

    try:
        out = await w.backfill_item_price_estimates({}, str(uid), "TestLeague", stash_only=True)
    finally:
        await fake_redis.aclose()

    assert out["ok"] is True
    assert out["estimated"] == 3
    assert saw_first_hybrid is True
