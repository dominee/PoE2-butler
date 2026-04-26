"""Per-character snapshot rows are cleared after manual refresh (see snapshot service)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.models import Snapshot, SnapshotKind, User
from app.services.snapshot import delete_character_snapshots, get_latest_snapshot


@pytest.mark.asyncio
async def test_delete_character_snapshots_removes_rows() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    uid = uuid.uuid4()
    async with factory() as session:
        session.add(
            User(
                id=uid,
                ggg_account_name="t#1",
                realm="pc",
            )
        )
        session.add(
            Snapshot(
                user_id=uid,
                kind=SnapshotKind.CHARACTER,
                key="Hero",
                payload={"character": {"name": "Hero"}, "items": []},
                fetched_at=datetime.now(UTC),
            )
        )
        await session.commit()

    async with factory() as session:
        snap = await get_latest_snapshot(session, uid, SnapshotKind.CHARACTER, "Hero")
        assert snap is not None
        await delete_character_snapshots(session, uid)
        await session.commit()

    async with factory() as session:
        res = await session.execute(
            select(Snapshot).where(
                Snapshot.user_id == uid,
                Snapshot.kind == SnapshotKind.CHARACTER,
            )
        )
        assert res.scalars().all() == []

    await engine.dispose()
