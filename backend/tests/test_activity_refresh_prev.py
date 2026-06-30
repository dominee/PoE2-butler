"""Activity diff baseline survives manual refresh re-insert."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.models import Snapshot, SnapshotKind, User
from app.services.snapshot import delete_character_snapshots, get_latest_snapshot, upsert_snapshot


def _payload(life: str) -> dict:
    return {
        "character": {"name": "Hero"},
        "items": [{"id": "x1", "explicitMods": [life], "itemData": {"id": "x1"}}],
    }


@pytest.mark.asyncio
async def test_refresh_reinsert_preserves_prev_for_activity() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    uid = uuid.uuid4()
    old = _payload("+10 life")
    new = _payload("+20 life")

    async with factory() as session:
        session.add(User(id=uid, ggg_account_name="t#1", realm="pc"))
        await upsert_snapshot(
            session, user_id=uid, kind=SnapshotKind.CHARACTER, key="Hero", payload=old
        )
        await session.commit()

    async with factory() as session:
        captured = await delete_character_snapshots(session, uid)
        await upsert_snapshot(
            session,
            user_id=uid,
            kind=SnapshotKind.CHARACTER,
            key="Hero",
            payload=new,
            previous_payload=captured["Hero"].payload,
            insert_prev_payload=captured["Hero"].payload,
        )
        await session.commit()

    async with factory() as session:
        snap = await get_latest_snapshot(session, uid, SnapshotKind.CHARACTER, "Hero")
        assert snap is not None
        assert snap.prev_payload != snap.payload
        assert snap.prev_payload["items"][0]["explicitMods"] == ["+10 life"]
        assert snap.payload["items"][0]["explicitMods"] == ["+20 life"]

    await engine.dispose()
