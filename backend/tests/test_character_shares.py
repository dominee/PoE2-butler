"""Character share link API (public read, auth create/revoke)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient

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
async def test_create_get_revoke_character_share(app_stack) -> None:  # type: ignore[no-untyped-def]
    _app, client, mock_app = app_stack
    await _full_login(client, mock_app)
    me = (await client.get("/api/me")).json()
    user_id = uuid.UUID(me["id"])
    fac = db_base._session_factory()
    async with fac() as session:
        session.add(
            Snapshot(
                user_id=user_id,
                kind=SnapshotKind.CHARACTER,
                key="Hero",
                payload=_char_payload("Hero"),
                fetched_at=datetime(2026, 6, 3, 12, 0, tzinfo=UTC),
            )
        )
        await session.commit()

    csrf = client.cookies.get("poe2b_csrf")
    assert csrf
    h = {"X-CSRF-Token": csrf, "Content-Type": "application/json"}
    r = await client.post(
        "/api/character-shares",
        json={
            "league": "Standard",
            "character_name": "Hero",
            "view_mode": "simple",
        },
        headers=h,
    )
    assert r.status_code == 201, r.text
    sid = r.json()["share_id"]

    pr = await AsyncClient(transport=ASGITransport(app=_app), base_url="http://testserver").get(
        f"/api/public/characters/{sid}"
    )
    assert pr.status_code == 200, pr.text
    body = pr.json()
    assert body["league"] == "Standard"
    assert body["character_name"] == "Hero"
    assert body["view_mode"] == "simple"
    assert body["character"]["summary"]["name"] == "Hero"

    dr = await client.delete(
        f"/api/character-shares/{sid}",
        headers={"X-CSRF-Token": csrf},
    )
    assert dr.status_code == 204

    pr2 = await AsyncClient(transport=ASGITransport(app=_app), base_url="http://testserver").get(
        f"/api/public/characters/{sid}"
    )
    assert pr2.status_code == 404


@pytest.mark.asyncio
async def test_character_share_historic_snapshot(app_stack) -> None:  # type: ignore[no-untyped-def]
    _app, client, mock_app = app_stack
    await _full_login(client, mock_app)
    me = (await client.get("/api/me")).json()
    user_id = uuid.UUID(me["id"])
    t0 = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)
    fac = db_base._session_factory()
    async with fac() as session:
        history_id = await archive_character_snapshot_if_changed(
            session,
            user_id=user_id,
            character_name="Hero",
            old_payload=_char_payload("Hero", life="+10 life"),
            new_payload=_char_payload("Hero", life="+30 life"),
            fetched_at=t0,
        )
        await session.commit()
    assert history_id is not None

    csrf = client.cookies.get("poe2b_csrf")
    assert csrf
    h = {"X-CSRF-Token": csrf, "Content-Type": "application/json"}
    r = await client.post(
        "/api/character-shares",
        json={
            "league": "Standard",
            "character_name": "Hero",
            "history_id": history_id,
            "view_mode": "detailed",
        },
        headers=h,
    )
    assert r.status_code == 201, r.text
    sid = r.json()["share_id"]

    pr = await AsyncClient(transport=ASGITransport(app=_app), base_url="http://testserver").get(
        f"/api/public/characters/{sid}"
    )
    assert pr.status_code == 200, pr.text
    body = pr.json()
    assert body["view_mode"] == "detailed"
    assert body["character"]["is_historical"] is True


@pytest.mark.asyncio
async def test_character_share_rate_limit(app_stack) -> None:  # type: ignore[no-untyped-def]
    _app, client, mock_app = app_stack
    await _full_login(client, mock_app)
    me = (await client.get("/api/me")).json()
    user_id = uuid.UUID(me["id"])
    fac = db_base._session_factory()
    async with fac() as session:
        session.add(
            Snapshot(
                user_id=user_id,
                kind=SnapshotKind.CHARACTER,
                key="Hero",
                payload=_char_payload("Hero"),
                fetched_at=datetime(2026, 6, 3, 12, 0, tzinfo=UTC),
            )
        )
        await session.commit()

    csrf = client.cookies.get("poe2b_csrf")
    assert csrf
    h = {"X-CSRF-Token": csrf, "Content-Type": "application/json"}
    for _ in range(10):
        r = await client.post(
            "/api/character-shares",
            json={
                "league": "Standard",
                "character_name": "Hero",
                "view_mode": "simple",
            },
            headers=h,
        )
        assert r.status_code == 201, r.text
    r11 = await client.post(
        "/api/character-shares",
        json={
            "league": "Standard",
            "character_name": "Hero",
            "view_mode": "simple",
        },
        headers=h,
    )
    assert r11.status_code == 429
