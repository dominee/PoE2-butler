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
