"""Tests for character snapshot history archive and timeline."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings
from app.db.base import Base
from app.db.models import CharacterSnapshotHistory, Snapshot, SnapshotKind, User
from app.services.character_snapshot_history import (
    archive_character_snapshot,
    get_character_snapshot_history,
    list_character_snapshots,
)
from app.services.snapshot import delete_character_snapshots, get_latest_snapshot, upsert_snapshot


def _char_payload(name: str, *, life: str = "+10 to maximum Life") -> dict:
    return {
        "character": {"name": name, "class": "Ranger", "level": 90, "league": "Standard"},
        "items": [
            {
                "id": "body1",
                "inventoryId": "BodyArmour",
                "name": "Test Chest",
                "baseType": "Leather Vest",
                "rarity": "Rare",
                "explicitMods": [life],
            }
        ],
    }


@pytest.fixture
async def db_factory(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("CHARACTER_SNAPSHOT_HISTORY_MAX", "20")
    get_settings.cache_clear()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    yield factory
    get_settings.cache_clear()
    await engine.dispose()


@pytest.fixture
async def user_id(db_factory) -> uuid.UUID:  # type: ignore[no-untyped-def]
    uid = uuid.uuid4()
    async with db_factory() as session:
        session.add(User(id=uid, ggg_account_name=f"hist_{uid.hex[:8]}#1", realm="pc"))
        await session.commit()
    return uid


@pytest.mark.asyncio
async def test_first_character_insert_does_not_archive(db_factory, user_id) -> None:  # type: ignore[no-untyped-def]
    payload = _char_payload("Hero")
    async with db_factory() as session:
        await upsert_snapshot(
            session,
            user_id=user_id,
            kind=SnapshotKind.CHARACTER,
            key="Hero",
            payload=payload,
        )
        await session.commit()

    async with db_factory() as session:
        res = await session.execute(select(CharacterSnapshotHistory))
        assert res.scalars().all() == []


@pytest.mark.asyncio
async def test_character_upsert_update_archives_old_payload(db_factory, user_id) -> None:  # type: ignore[no-untyped-def]
    t0 = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)
    t1 = datetime(2026, 6, 2, 12, 0, tzinfo=UTC)
    async with db_factory() as session:
        session.add(
            Snapshot(
                user_id=user_id,
                kind=SnapshotKind.CHARACTER,
                key="Hero",
                payload=_char_payload("Hero", life="+10 to maximum Life"),
                fetched_at=t0,
            )
        )
        await session.commit()

    async with db_factory() as session:
        snap = await get_latest_snapshot(session, user_id, SnapshotKind.CHARACTER, "Hero")
        assert snap is not None
        snap.fetched_at = t0
        await upsert_snapshot(
            session,
            user_id=user_id,
            kind=SnapshotKind.CHARACTER,
            key="Hero",
            payload=_char_payload("Hero", life="+20 to maximum Life"),
        )
        snap_after = await get_latest_snapshot(session, user_id, SnapshotKind.CHARACTER, "Hero")
        assert snap_after is not None
        snap_after.fetched_at = t1
        await session.commit()

    async with db_factory() as session:
        res = await session.execute(
            select(CharacterSnapshotHistory).where(CharacterSnapshotHistory.character_name == "Hero")
        )
        rows = list(res.scalars().all())
        assert len(rows) == 1
        assert rows[0].fetched_at.replace(tzinfo=UTC) == t0
        assert rows[0].payload["items"][0]["explicitMods"] == ["+10 to maximum Life"]


@pytest.mark.asyncio
async def test_delete_character_snapshots_archives_before_delete(
    db_factory, user_id
) -> None:  # type: ignore[no-untyped-def]
    t0 = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)
    payload = _char_payload("Hero")
    async with db_factory() as session:
        session.add(
            Snapshot(
                user_id=user_id,
                kind=SnapshotKind.CHARACTER,
                key="Hero",
                payload=payload,
                fetched_at=t0,
            )
        )
        await session.commit()

    async with db_factory() as session:
        await delete_character_snapshots(session, user_id)
        await session.commit()

    async with db_factory() as session:
        snap = await get_latest_snapshot(session, user_id, SnapshotKind.CHARACTER, "Hero")
        assert snap is None
        res = await session.execute(select(CharacterSnapshotHistory))
        rows = list(res.scalars().all())
        assert len(rows) == 1
        assert rows[0].payload == payload
        assert rows[0].fetched_at.replace(tzinfo=UTC) == t0


@pytest.mark.asyncio
async def test_prune_keeps_newest_twenty(db_factory, user_id, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("CHARACTER_SNAPSHOT_HISTORY_MAX", "3")
    get_settings.cache_clear()
    base = datetime(2026, 1, 1, tzinfo=UTC)
    async with db_factory() as session:
        for i in range(4):
            await archive_character_snapshot(
                session,
                user_id=user_id,
                character_name="Hero",
                payload=_char_payload("Hero", life=f"+{i} life"),
                fetched_at=base + timedelta(days=i),
            )
        await session.commit()

    async with db_factory() as session:
        res = await session.execute(
            select(CharacterSnapshotHistory)
            .where(CharacterSnapshotHistory.character_name == "Hero")
            .order_by(CharacterSnapshotHistory.fetched_at.asc())
        )
        rows = list(res.scalars().all())
        assert len(rows) == 3
        assert rows[0].payload["items"][0]["explicitMods"] == ["+1 life"]
        assert rows[-1].payload["items"][0]["explicitMods"] == ["+3 life"]


@pytest.mark.asyncio
async def test_refresh_simulation_delete_then_insert_one_history(
    db_factory, user_id
) -> None:  # type: ignore[no-untyped-def]
    async with db_factory() as session:
        await upsert_snapshot(
            session,
            user_id=user_id,
            kind=SnapshotKind.CHARACTER,
            key="Hero",
            payload=_char_payload("Hero", life="+10 life"),
        )
        await session.commit()

    async with db_factory() as session:
        await delete_character_snapshots(session, user_id)
        await upsert_snapshot(
            session,
            user_id=user_id,
            kind=SnapshotKind.CHARACTER,
            key="Hero",
            payload=_char_payload("Hero", life="+20 life"),
        )
        await session.commit()

    async with db_factory() as session:
        res = await session.execute(select(CharacterSnapshotHistory))
        assert len(list(res.scalars().all())) == 1


@pytest.mark.asyncio
async def test_list_character_snapshots_order_and_current(db_factory, user_id) -> None:  # type: ignore[no-untyped-def]
    t0 = datetime(2026, 6, 1, tzinfo=UTC)
    t2 = datetime(2026, 6, 3, tzinfo=UTC)
    async with db_factory() as session:
        await archive_character_snapshot(
            session,
            user_id=user_id,
            character_name="Hero",
            payload=_char_payload("Hero", life="+10 life"),
            fetched_at=t0,
        )
        session.add(
            Snapshot(
                user_id=user_id,
                kind=SnapshotKind.CHARACTER,
                key="Hero",
                payload=_char_payload("Hero", life="+30 life"),
                fetched_at=t2,
            )
        )
        await session.commit()

    async with db_factory() as session:
        meta = await list_character_snapshots(session, user_id=user_id, character_name="Hero")
        assert len(meta) == 2
        assert meta[0].is_current is False
        assert meta[0].fetched_at.replace(tzinfo=UTC) == t0
        assert meta[1].is_current is True
        assert meta[1].fetched_at.replace(tzinfo=UTC) == t2
        assert meta[1].id is None


@pytest.mark.asyncio
async def test_get_character_snapshot_history_cross_user_isolation(
    db_factory, user_id
) -> None:  # type: ignore[no-untyped-def]
    other = uuid.uuid4()
    async with db_factory() as session:
        session.add(User(id=other, ggg_account_name=f"other_{other.hex[:8]}#1", realm="pc"))
        await archive_character_snapshot(
            session,
            user_id=user_id,
            character_name="Hero",
            payload=_char_payload("Hero"),
            fetched_at=datetime.now(UTC),
        )
        await session.commit()
        res = await session.execute(select(CharacterSnapshotHistory))
        hist_id = res.scalar_one().id

    async with db_factory() as session:
        assert (
            await get_character_snapshot_history(
                session, user_id=other, character_name="Hero", history_id=hist_id
            )
            is None
        )
        row = await get_character_snapshot_history(
            session, user_id=user_id, character_name="Hero", history_id=hist_id
        )
        assert row is not None
