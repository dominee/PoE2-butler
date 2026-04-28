"""Async price estimate REST (mocked queue)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from tests.test_auth_flow import _full_login


@pytest.mark.asyncio
async def test_start_estimate_enqueues_job(app_stack) -> None:
    _app, client, mock_app = app_stack
    await _full_login(client, mock_app)
    csrf = client.cookies.get("poe2b_csrf")
    item = {
        "id": "r1",
        "inventory_id": "S",
        "w": 1,
        "h": 1,
        "name": "",
        "type_line": "Iron Ring",
        "base_type": "Iron Ring",
        "rarity": "Rare",
        "ilvl": 82,
        "identified": True,
        "corrupted": False,
        "properties": [],
        "requirements": [],
        "implicit_mods": [],
        "explicit_mods": ["+20 to maximum Life", "+8% to all Elemental Resistances"],
        "rune_mods": [],
        "enchant_mods": [],
        "crafted_mods": [],
        "sockets": [],
        "stack_size": None,
        "max_stack_size": None,
        "icon": None,
    }
    with patch("app.api.pricing.get_arq_pool", new_callable=AsyncMock) as mpool:
        mpool.return_value.enqueue_job = AsyncMock()
        resp = await client.post(
            "/api/pricing/estimate",
            json={"league": "Dawn of the Hunt", "item": item},
            headers={"X-CSRF-Token": csrf} if csrf else {},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert "job_id" in body
        mpool.return_value.enqueue_job.assert_called_once()
