"""GET /api/activity: diff prev vs current stash tab snapshots."""

from __future__ import annotations

import uuid
from typing import Any

import pytest

from app.api.activity import _diff_tab, _item_changed
from app.db import base as db_base
from app.db.models import Snapshot, SnapshotKind
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
    assert _item_changed(a, b) is True
    c = {**_MIN, "id": "x", "name": "A", "explicitMods": ["+1 to life"]}
    assert _item_changed(a, c) is False


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
    new_i, chg, rem = _diff_tab(prev, new)
    assert [x.id for x in new_i] == ["add"]
    assert [c.old.id for c in chg] == [c.new.id for c in chg] == ["keep"]
    assert [x.id for x in rem] == ["gone"]


@pytest.mark.asyncio
async def test_activity_get_requires_auth(app_stack) -> None:  # type: ignore[no-untyped-def]
    _app, client, _mock = app_stack
    r = await client.get("/api/activity", params={"league": LEAGUE})
    assert r.status_code == 401


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
