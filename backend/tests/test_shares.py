"""Item share link API (public read, auth create/revoke)."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from tests.test_auth_flow import _full_login

_MIN_ITEM = {
    "id": "share-test-1",
    "w": 1,
    "h": 1,
    "name": "Test Item",
    "typeLine": "Stellar Amulet",
    "baseType": "Stellar Amulet",
    "frameType": 2,
    "ilvl": 80,
    "rarity": "Rare",
    "implicitMods": ["+10 to life"],
    "explicitMods": ["+20 to Strength"],
    "properties": [],
    "requirements": [],
    "sockets": [],
    "verified": True,
    "corrupted": False,
    "identified": True,
}


@pytest.mark.asyncio
async def test_create_get_revoke_share(app_stack) -> None:  # type: ignore[no-untyped-def]
    _app, client, mock_app = app_stack
    await _full_login(client, mock_app)
    csrf = client.cookies.get("poe2b_csrf")
    assert csrf
    h = {"X-CSRF-Token": csrf, "Content-Type": "application/json"}
    r = await client.post(
        "/api/shares",
        json={"league": "Fate of the Vaal", "item": _MIN_ITEM},
        headers=h,
    )
    assert r.status_code == 201, r.text
    sid = r.json()["share_id"]

    pr = await AsyncClient(transport=ASGITransport(app=_app), base_url="http://testserver").get(
        f"/api/public/items/{sid}"
    )
    assert pr.status_code == 200, pr.text
    body = pr.json()
    assert body["league"] == "Fate of the Vaal"
    assert body["item"]["name"] == "Test Item"

    dr = await client.delete(
        f"/api/shares/{sid}",
        headers={"X-CSRF-Token": csrf},
    )
    assert dr.status_code == 204

    pr2 = await AsyncClient(transport=ASGITransport(app=_app), base_url="http://testserver").get(
        f"/api/public/items/{sid}"
    )
    assert pr2.status_code == 404


@pytest.mark.asyncio
async def test_share_rate_limit(app_stack) -> None:  # type: ignore[no-untyped-def]
    _app, client, mock_app = app_stack
    await _full_login(client, mock_app)
    csrf = client.cookies.get("poe2b_csrf")
    assert csrf
    h = {"X-CSRF-Token": csrf, "Content-Type": "application/json"}
    for n in range(10):
        r = await client.post(
            "/api/shares",
            json={"league": "Fate of the Vaal", "item": {**_MIN_ITEM, "id": f"r{n}"}},
            headers=h,
        )
        assert r.status_code == 201, r.text
    r11 = await client.post(
        "/api/shares",
        json={"league": "Fate of the Vaal", "item": {**_MIN_ITEM, "id": "r10"}},
        headers=h,
    )
    assert r11.status_code == 429


_MIN_ITEM_API = {
    "id": "api-shaped-1",
    "inventory_id": "tab1",
    "w": 1,
    "h": 1,
    "name": "API Shaped",
    "type_line": "Stellar Amulet",
    "base_type": "Stellar Amulet",
    "rarity": "Rare",
    "ilvl": 80,
    "identified": True,
    "corrupted": False,
    "properties": [],
    "requirements": [],
    "implicit_mods": ["+10 to life"],
    "implicit_mod_details": [],
    "explicit_mods": ["+20 to Strength"],
    "explicit_mod_details": [
        {
            "name": "of Shelling",
            "tier": 2,
            "level": 55,
            "magnitudes": [{"hash": "h1", "min": 1.0, "max": 1.0, "t1_max": 2.0}],
            "all_tiers": [
                {
                    "tier_ggg": 1,
                    "required_level": 82,
                    "name": "of Bursting",
                    "stats": [{"id": "base_number_of_crossbow_bolts", "min": 2, "max": 2}],
                },
                {
                    "tier_ggg": 2,
                    "required_level": 55,
                    "name": "of Shelling",
                    "stats": [{"id": "base_number_of_crossbow_bolts", "min": 1, "max": 1}],
                },
            ],
        }
    ],
    "socketed_items": [
        {
            "id": "rune-api-1",
            "inventory_id": None,
            "w": 1,
            "h": 1,
            "x": None,
            "y": None,
            "item_class": None,
            "name": "",
            "type_line": "Iron Rune",
            "base_type": "Iron Rune",
            "rarity": "Currency",
            "ilvl": None,
            "identified": True,
            "corrupted": False,
            "flavour_text": None,
            "implicit_mod_range_hints": [],
            "explicit_mod_range_hints": [],
            "trailer_note": None,
            "properties": [],
            "requirements": [],
            "implicit_mods": [],
            "implicit_mod_details": [],
            "explicit_mods": ["+5 to Strength"],
            "explicit_mod_details": [],
            "rune_mods": [],
            "enchant_mods": [],
            "crafted_mods": [],
            "sockets": [],
            "socketed_items": [],
            "stack_size": None,
            "max_stack_size": None,
            "icon": None,
        }
    ],
    "rune_mods": [],
    "enchant_mods": [],
    "crafted_mods": [],
    "sockets": [{"group": 0, "type": "rune"}],
    "stack_size": None,
    "max_stack_size": None,
    "icon": None,
}


@pytest.mark.asyncio
async def test_create_share_accepts_spa_item_json(app_stack) -> None:  # type: ignore[no-untyped-def]
    _app, client, mock_app = app_stack
    await _full_login(client, mock_app)
    csrf = client.cookies.get("poe2b_csrf")
    assert csrf
    h = {"X-CSRF-Token": csrf, "Content-Type": "application/json"}
    r = await client.post(
        "/api/shares",
        json={"league": "Fate of the Vaal", "item": _MIN_ITEM_API},
        headers=h,
    )
    assert r.status_code == 201, r.text
    sid = r.json()["share_id"]
    pr = await AsyncClient(transport=ASGITransport(app=_app), base_url="http://testserver").get(
        f"/api/public/items/{sid}"
    )
    assert pr.status_code == 200, pr.text
    assert pr.json()["item"]["name"] == "API Shaped"
