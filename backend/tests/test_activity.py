"""GET /api/activity: diff prev vs current stash tab snapshots."""

from __future__ import annotations

import uuid
from typing import Any

import pytest

from app.api.activity import _character_league
from app.domain.snapshot_diff import diff_payloads, item_changed
from app.db import base as db_base
from app.db.models import Snapshot, SnapshotKind
from app.services.snapshot import upsert_snapshot
from tests.test_auth_flow import _full_login

LEAGUE = "Dawn of the Hunt"
TAB_KEY = f"{LEAGUE}:activity_test_tab"

_MIN = {
    "w": 1,
    "h": 1,
    "rarity": "Normal",
    "typeLine": "Rusted Sword",
    "baseType": "Rusted Sword",
    "corrupted": False,
    "identified": True,
}


def _raw_item(oid: str, name: str, life_mod: str) -> dict[str, Any]:
    return {**_MIN, "id": oid, "name": name, "explicitMods": [life_mod]}


def _tab_payload(
    name: str,
    items: list[dict[str, Any]],
) -> dict[str, Any]:
    return {"tab": {"id": "t_act", "name": name}, "items": items}


def test_item_changed_detects_explicit_mod() -> None:
    a = {**_MIN, "id": "x", "name": "A", "explicitMods": ["+1 to life"]}
    b = {**_MIN, "id": "x", "name": "A", "explicitMods": ["+2 to life"]}
    assert item_changed(a, b) is True
    c = {**_MIN, "id": "x", "name": "A", "explicitMods": ["+1 to life"]}
    assert item_changed(a, c) is False


def test_diff_tab_new_changed_removed() -> None:
    prev = _tab_payload(
        "T",
        [
            _raw_item("keep", "K", "+5 to life"),
            _raw_item("gone", "G", "+10 to life"),
        ],
    )
    new = _tab_payload(
        "T",
        [
            {**_raw_item("keep", "K", "+5 to life"), "explicitMods": ["+6 to life"]},
            _raw_item("add", "N", "+1 to life"),
        ],
    )
    new_i, chg, rem = diff_payloads(prev, new)
    assert [x.id for x in new_i] == ["add"]
    assert [c.old.id for c in chg] == [c.new.id for c in chg] == ["keep"]
    assert [x.id for x in rem] == ["gone"]


@pytest.mark.asyncio
async def test_activity_get_requires_auth(app_stack) -> None:  # type: ignore[no-untyped-def]
    _app, client, _mock = app_stack
    r = await client.get("/api/activity", params={"league": LEAGUE})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_activity_upsert_insert_has_prev_baseline(app_stack) -> None:  # type: ignore[no-untyped-def]
    """First stash tab write seeds prev_payload so activity is tracked (diff may be empty)."""
    _app, client, mock_app = app_stack
    await _full_login(client, mock_app)
    me = (await client.get("/api/me")).json()
    user_id = uuid.UUID(me["id"])
    fac = db_base._session_factory()
    tab = _tab_payload("Seed", [_raw_item("seed1", "S", "+1 to life")])
    async with fac() as session:
        await upsert_snapshot(
            session,
            user_id=user_id,
            kind=SnapshotKind.STASH_TAB,
            key=TAB_KEY,
            payload=tab,
        )
        await session.commit()

    r = await client.get("/api/activity", params={"league": LEAGUE})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["has_prev"] is True
    assert body["total_new"] == 0
    assert body["total_changed"] == 0
    assert body["entries"] == []


@pytest.mark.asyncio
async def test_activity_no_prev_is_empty_not_has_prev(app_stack) -> None:  # type: ignore[no-untyped-def]
    """When prev_payload is missing, that tab is skipped; has_prev stays false."""
    _app, client, mock_app = app_stack
    await _full_login(client, mock_app)
    me = (await client.get("/api/me")).json()
    user_id = uuid.UUID(me["id"])
    fac = db_base._session_factory()
    prev_tab = _tab_payload("Lone", [_raw_item("a", "A", "+1 to life")])
    async with fac() as session:
        session.add(
            Snapshot(
                user_id=user_id,
                kind=SnapshotKind.STASH_TAB,
                key=TAB_KEY,
                payload=prev_tab,
                prev_payload=None,
            )
        )
        await session.commit()

    r = await client.get("/api/activity", params={"league": LEAGUE})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["league"] == LEAGUE
    assert body["has_prev"] is False
    assert body["total_new"] == 0
    assert body["total_changed"] == 0
    assert body["entries"] == []


@pytest.mark.asyncio
async def test_activity_sums_new_and_changed(app_stack) -> None:  # type: ignore[no-untyped-def]
    _app, client, mock_app = app_stack
    await _full_login(client, mock_app)
    me = (await client.get("/api/me")).json()
    user_id = uuid.UUID(me["id"])
    fac = db_base._session_factory()
    pprev = _tab_payload(
        "T",
        [
            _raw_item("keep", "K", "+5 to life"),
            _raw_item("gone", "G", "+1 to life"),
        ],
    )
    pnew = _tab_payload(
        "T",
        [
            {**_raw_item("keep", "K", "+5 to life"), "explicitMods": ["+6 to life"]},
            _raw_item("add", "N", "+1 to life"),
        ],
    )
    async with fac() as session:
        session.add(
            Snapshot(
                user_id=user_id,
                kind=SnapshotKind.STASH_TAB,
                key=TAB_KEY,
                payload=pnew,
                prev_payload=pprev,
            )
        )
        await session.commit()

    r = await client.get("/api/activity", params={"league": LEAGUE})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["has_prev"] is True
    assert body["total_new"] == 1
    assert body["total_changed"] == 1
    assert len(body["entries"]) == 1
    ent = body["entries"][0]
    assert ent["tab_id"] == "activity_test_tab"
    assert ent["tab_name"] == "T"
    assert {i["id"] for i in ent["new_items"]} == {"add"}
    assert {c["old"]["id"] for c in ent["changed_items"]} == {"keep"}
    assert {c["new"]["id"] for c in ent["changed_items"]} == {"keep"}
    assert {i["id"] for i in ent["removed_items"]} == {"gone"}


@pytest.mark.asyncio
async def test_activity_empty_stash_list(app_stack) -> None:  # type: ignore[no-untyped-def]
    _app, client, mock_app = app_stack
    await _full_login(client, mock_app)
    r = await client.get("/api/activity", params={"league": LEAGUE})
    assert r.status_code == 200
    body = r.json()
    assert body["has_prev"] is False
    assert body["total_new"] == 0
    assert body["entries"] == []


# ── character gear diffs ─────────────────────────────────────────────────────


def _char_payload(
    name: str,
    league: str,
    items: list[dict[str, Any]],
) -> dict[str, Any]:
    return {"character": {"id": name, "name": name, "league": league}, "items": items}


def _raw_gear(oid: str, slot: str, life_mod: str) -> dict[str, Any]:
    return {
        **_MIN,
        "id": oid,
        "name": f"Item-{oid}",
        "inventoryId": slot,
        "explicitMods": [life_mod],
    }


def test_character_league_helper() -> None:
    payload = {"character": {"name": "X", "league": "Fate of the Vaal"}, "items": []}
    assert _character_league(payload) == "Fate of the Vaal"
    assert _character_league({}) == ""


@pytest.mark.asyncio
async def test_activity_gear_diff_new_item(app_stack) -> None:  # type: ignore[no-untyped-def]
    """Equipping a new weapon shows up in gear_entries.new_items."""
    _app, client, mock_app = app_stack
    await _full_login(client, mock_app)
    me = (await client.get("/api/me")).json()
    user_id = uuid.UUID(me["id"])
    fac = db_base._session_factory()

    pprev = _char_payload("Slayer", LEAGUE, [])
    pnew = _char_payload("Slayer", LEAGUE, [_raw_gear("w1", "Weapon", "+100 to maximum Life")])

    async with fac() as session:
        session.add(
            Snapshot(
                user_id=user_id,
                kind=SnapshotKind.CHARACTER,
                key="Slayer",
                payload=pnew,
                prev_payload=pprev,
            )
        )
        await session.commit()

    r = await client.get("/api/activity", params={"league": LEAGUE})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["has_prev"] is True
    assert body["total_new"] == 1
    assert len(body["gear_entries"]) == 1
    ge = body["gear_entries"][0]
    assert ge["tab_id"] == "Slayer"
    assert ge["tab_name"] == "Slayer"
    assert len(ge["new_items"]) == 1
    assert ge["new_items"][0]["id"] == "w1"
    assert ge["changed_items"] == []
    assert ge["removed_items"] == []


@pytest.mark.asyncio
async def test_activity_gear_diff_changed_item(app_stack) -> None:  # type: ignore[no-untyped-def]
    """A mod change on an equipped item shows up in gear_entries.changed_items."""
    _app, client, mock_app = app_stack
    await _full_login(client, mock_app)
    me = (await client.get("/api/me")).json()
    user_id = uuid.UUID(me["id"])
    fac = db_base._session_factory()

    pprev = _char_payload("Witch", LEAGUE, [_raw_gear("helm1", "Helm", "+50 to maximum Life")])
    pnew = _char_payload("Witch", LEAGUE, [_raw_gear("helm1", "Helm", "+60 to maximum Life")])

    async with fac() as session:
        session.add(
            Snapshot(
                user_id=user_id,
                kind=SnapshotKind.CHARACTER,
                key="Witch",
                payload=pnew,
                prev_payload=pprev,
            )
        )
        await session.commit()

    r = await client.get("/api/activity", params={"league": LEAGUE})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total_changed"] >= 1
    gear = body["gear_entries"]
    witch_entry = next(g for g in gear if g["tab_id"] == "Witch")
    assert len(witch_entry["changed_items"]) == 1
    assert witch_entry["changed_items"][0]["old"]["id"] == "helm1"
    assert witch_entry["changed_items"][0]["new"]["id"] == "helm1"


@pytest.mark.asyncio
async def test_activity_gear_excluded_for_different_league(app_stack) -> None:  # type: ignore[no-untyped-def]
    """Character in a different league does not appear in the activity response."""
    _app, client, mock_app = app_stack
    await _full_login(client, mock_app)
    me = (await client.get("/api/me")).json()
    user_id = uuid.UUID(me["id"])
    fac = db_base._session_factory()

    pprev = _char_payload("Standard_Char", "Standard", [])
    pnew = _char_payload(
        "Standard_Char", "Standard", [_raw_gear("s1", "Weapon", "+1 to life")]
    )

    async with fac() as session:
        session.add(
            Snapshot(
                user_id=user_id,
                kind=SnapshotKind.CHARACTER,
                key="Standard_Char",
                payload=pnew,
                prev_payload=pprev,
            )
        )
        await session.commit()

    r = await client.get("/api/activity", params={"league": LEAGUE})
    assert r.status_code == 200, r.text
    body = r.json()
    gear_ids = [g["tab_id"] for g in body["gear_entries"]]
    assert "Standard_Char" not in gear_ids


@pytest.mark.asyncio
async def test_activity_response_includes_gear_entries_field(app_stack) -> None:  # type: ignore[no-untyped-def]
    """The response always includes the gear_entries key (empty list when no gear diffs)."""
    _app, client, mock_app = app_stack
    await _full_login(client, mock_app)
    r = await client.get("/api/activity", params={"league": LEAGUE})
    assert r.status_code == 200
    body = r.json()
    assert "gear_entries" in body
    assert isinstance(body["gear_entries"], list)
