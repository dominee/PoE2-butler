"""GET /api/characters/{name}/snapshots and historic detail."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from app.db import base as db_base
from app.db.models import Snapshot, SnapshotKind
from app.services.character_snapshot_history import archive_character_snapshot_if_changed
from tests.test_auth_flow import _full_login


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


@pytest.mark.asyncio
async def test_character_snapshots_requires_auth(app_stack) -> None:  # type: ignore[no-untyped-def]
    _app, client, _mock = app_stack
    r = await client.get("/api/characters/Hero/snapshots")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_character_snapshots_list_includes_changes(app_stack) -> None:  # type: ignore[no-untyped-def]
    _app, client, mock_app = app_stack
    await _full_login(client, mock_app)
    me = (await client.get("/api/me")).json()
    user_id = uuid.UUID(me["id"])
    t0 = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)
    t1 = datetime(2026, 6, 3, 12, 0, tzinfo=UTC)
    fac = db_base._session_factory()
    async with fac() as session:
        await archive_character_snapshot_if_changed(
            session,
            user_id=user_id,
            character_name="Hero",
            old_payload=_char_payload("Hero", life="+10 life"),
            new_payload=_char_payload("Hero", life="+30 life"),
            fetched_at=t0,
        )
        session.add(
            Snapshot(
                user_id=user_id,
                kind=SnapshotKind.CHARACTER,
                key="Hero",
                payload=_char_payload("Hero", life="+30 life"),
                fetched_at=t1,
            )
        )
        await session.commit()

    r = await client.get("/api/characters/Hero/snapshots")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["character_name"] == "Hero"
    assert len(body["snapshots"]) == 1
    snap = body["snapshots"][0]
    assert snap["is_current"] is True
    assert snap["changes"] == [{"kind": "changed", "label": "Test Chest"}]
    assert "2026-06-01" in snap["fetched_at"]


@pytest.mark.asyncio
async def test_historic_character_detail(app_stack) -> None:  # type: ignore[no-untyped-def]
    _app, client, mock_app = app_stack
    await _full_login(client, mock_app)
    me = (await client.get("/api/me")).json()
    user_id = uuid.UUID(me["id"])
    fac = db_base._session_factory()
    async with fac() as session:
        await archive_character_snapshot_if_changed(
            session,
            user_id=user_id,
            character_name="Hero",
            old_payload=_char_payload("Hero", life="+10 life"),
            new_payload=_char_payload("Hero", life="+55 life"),
            fetched_at=datetime(2026, 6, 1, tzinfo=UTC),
        )
        await session.commit()
        from sqlalchemy import select

        from app.db.models import CharacterSnapshotHistory

        res = await session.execute(select(CharacterSnapshotHistory))
        hist_id = res.scalar_one().id

    r = await client.get(f"/api/characters/Hero/snapshots/{hist_id}")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["is_historical"] is True
    assert body["snapshot_fetched_at"] is not None
    assert body["equipped"][0]["explicit_mods"] == ["+55 life"]
    assert body["stat_summary"]["sections"]


@pytest.mark.asyncio
async def test_historic_character_not_found(app_stack) -> None:  # type: ignore[no-untyped-def]
    _app, client, mock_app = app_stack
    await _full_login(client, mock_app)
    r = await client.get("/api/characters/Hero/snapshots/999999")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_historic_character_wrong_character_name(app_stack) -> None:  # type: ignore[no-untyped-def]
    _app, client, mock_app = app_stack
    await _full_login(client, mock_app)
    me = (await client.get("/api/me")).json()
    user_id = uuid.UUID(me["id"])
    fac = db_base._session_factory()
    async with fac() as session:
        await archive_character_snapshot_if_changed(
            session,
            user_id=user_id,
            character_name="Hero",
            old_payload=_char_payload("Hero", life="+1 life"),
            new_payload=_char_payload("Hero", life="+2 life"),
            fetched_at=datetime.now(UTC),
        )
        await session.commit()
        from sqlalchemy import select

        from app.db.models import CharacterSnapshotHistory

        res = await session.execute(select(CharacterSnapshotHistory))
        hist_id = res.scalar_one().id

    r = await client.get(f"/api/characters/OtherHero/snapshots/{hist_id}")
    assert r.status_code == 404
