"""API: PoE2-style item text (clipboard)."""

from __future__ import annotations

import pytest

from app.domain.item import Item
from app.domain.item_text import format_item_text
from tests.test_auth_flow import _full_login


def _sample_item() -> dict:
    return {
        "id": "i1",
        "inventory_id": "Weapon",
        "w": 2,
        "h": 4,
        "x": None,
        "y": None,
        "name": "Doom Horn",
        "type_line": "Spine Bow",
        "base_type": "Spine Bow",
        "rarity": "Rare",
        "ilvl": 82,
        "identified": True,
        "corrupted": False,
        "properties": [],
        "requirements": [],
        "implicit_mods": [],
        "explicit_mods": ["+100 to maximum Life"],
        "rune_mods": [],
        "enchant_mods": [],
        "crafted_mods": [],
        "sockets": [],
        "stack_size": None,
        "max_stack_size": None,
        "icon": None,
    }


@pytest.mark.asyncio
async def test_item_text_requires_auth(app_stack) -> None:  # type: ignore[no-untyped-def]
    _app, client, _mock_app = app_stack
    resp = await client.post(
        "/api/items/item-text",
        json={"item": _sample_item()},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_item_text_returns_poe2_block(app_stack) -> None:  # type: ignore[no-untyped-def]
    _app, client, mock_app = app_stack
    await _full_login(client, mock_app)
    data = _sample_item()
    resp = await client.post(
        "/api/items/item-text",
        json={"item": data},
    )
    assert resp.status_code == 200, resp.text
    text = resp.json()["text"]
    expected = format_item_text(Item.model_validate(data))
    assert text == expected
    assert "Rarity:" in text
    assert "Doom Horn" in text
    assert "maximum Life" in text
