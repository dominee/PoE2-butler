"""Character gear refresh resilience against GGG rate limits."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.clients.ggg import GGGClient, GGGError
from app.db.base import Base
from app.db.models import SnapshotKind, User
from app.security.crypto import TokenCipher
from app.services.snapshot import (
    CapturedCharacterSnapshot,
    ensure_character_detail,
    get_latest_snapshot,
    refresh_character_gear_snapshots,
    restore_character_snapshot,
    upsert_snapshot,
)


def _char_payload(name: str, life: str = "+10 life") -> dict:
    return {
        "character": {"name": name, "league": "TestLeague"},
        "items": [{"id": "x1", "explicitMods": [life], "itemData": {"id": "x1"}}],
    }


@pytest.mark.asyncio
async def test_restore_character_snapshot_reinserts_cache() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    uid = uuid.uuid4()
    captured = CapturedCharacterSnapshot(
        payload=_char_payload("Hero"),
        prev_payload=_char_payload("Hero", "+5 life"),
        fetched_at=datetime(2026, 6, 1, 12, 0, tzinfo=UTC),
    )

    async with factory() as session:
        session.add(User(id=uid, ggg_account_name="t#1", realm="pc"))
        await restore_character_snapshot(session, user_id=uid, name="Hero", captured=captured)
        await session.commit()

    async with factory() as session:
        snap = await get_latest_snapshot(session, uid, SnapshotKind.CHARACTER, "Hero")
        assert snap is not None
        assert snap.payload["items"][0]["explicitMods"] == ["+10 life"]

    await engine.dispose()


@pytest.mark.asyncio
async def test_refresh_character_gear_restores_on_ggg_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    uid = uuid.uuid4()
    user = User(id=uid, ggg_account_name="t#1", realm="pc", preferred_league="TestLeague")
    captured = CapturedCharacterSnapshot(payload=_char_payload("Hero"), prev_payload=None)

    async with factory() as session:
        session.add(user)
        await upsert_snapshot(
            session,
            user_id=uid,
            kind=SnapshotKind.CHARACTERS,
            key="",
            payload={"characters": [{"name": "Hero", "league": "TestLeague"}]},
        )
        await session.commit()

    ggg = AsyncMock(spec=GGGClient)
    ggg.get_character.side_effect = GGGError(
        429, {"error": {"code": 3, "message": "Rate limit exceeded"}}
    )
    cipher = AsyncMock(spec=TokenCipher)

    monkeypatch.setattr(
        "app.services.snapshot.get_settings",
        lambda: type("S", (), {"ggg_character_fetch_spacing_sec": 0.0})(),
    )
    monkeypatch.setattr(
        "app.services.snapshot.ensure_character_detail",
        AsyncMock(side_effect=GGGError(429, {"error": {"code": 3}})),
    )

    async with factory() as session:
        session.add(user)
        await refresh_character_gear_snapshots(
            session=session,
            user=user,
            ggg=ggg,
            cipher=cipher,
            league="TestLeague",
            captured_characters={"Hero": captured},
        )
        await session.commit()

    async with factory() as session:
        snap = await get_latest_snapshot(session, uid, SnapshotKind.CHARACTER, "Hero")
        assert snap is not None
        assert snap.payload["character"]["name"] == "Hero"

    await engine.dispose()


@pytest.mark.asyncio
async def test_ensure_character_detail_serves_stale_on_429(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    uid = uuid.uuid4()
    user = User(id=uid, ggg_account_name="t#1", realm="pc")
    stale = _char_payload("Hero", "+10 life")

    async with factory() as session:
        session.add(user)
        await upsert_snapshot(
            session,
            user_id=uid,
            kind=SnapshotKind.CHARACTER,
            key="Hero",
            payload=stale,
        )
        await session.commit()

    ggg = AsyncMock(spec=GGGClient)
    ggg.get_character.side_effect = GGGError(429, {"error": {"code": 3}})
    cipher = AsyncMock(spec=TokenCipher)

    monkeypatch.setattr(
        "app.services.snapshot.get_valid_ggg_access",
        AsyncMock(return_value="token"),
    )
    monkeypatch.setattr(
        "app.services.snapshot._character_detail_snapshot_ttl_seconds",
        lambda _payload: 0.0,
    )

    async with factory() as session:
        session.add(user)
        payload = await ensure_character_detail(
            session=session,
            user=user,
            ggg=ggg,
            cipher=cipher,
            name="Hero",
        )
        assert payload["items"][0]["explicitMods"] == ["+10 life"]
        ggg.get_character.assert_awaited_once()

    await engine.dispose()
