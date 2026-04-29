"""Async price estimate REST (mocked queue)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch
from urllib.parse import quote

import pytest

from app.db import base as db_base
from app.db.models import ItemPriceEstimate
from app.services.pricing.source import PriceEstimate, PriceUnit

from tests.test_auth_flow import _full_login


@pytest.mark.asyncio
async def test_get_persisted_estimate_item_204(app_stack) -> None:
    _app, client, mock_app = app_stack
    await _full_login(client, mock_app)
    resp = await client.get(
        "/api/pricing/estimate/item?league=Dawn+of+the+Hunt&item_id=r1&tolerance_pct=10",
    )
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_get_persisted_estimate_item_200(app_stack) -> None:
    _app, client, mock_app = app_stack
    await _full_login(client, mock_app)
    me = await client.get("/api/me")
    assert me.status_code == 200
    import uuid as uuid_mod

    user_id = uuid_mod.UUID(me.json()["id"])
    est = PriceEstimate(
        value=12.0,
        unit=PriceUnit.CHAOS,
        chaos_equiv=12.0,
        source="test",
        estimate_method="trade_median",
        sample_size=5,
    )
    factory = db_base._session_factory()
    async with factory() as session:
        session.add(
            ItemPriceEstimate(
                user_id=user_id,
                league="Dawn of the Hunt",
                item_id="r1",
                tolerance_pct=10.0,
                item_name="Test",
                status="completed",
                message="ok",
                result_json=est.model_dump(mode="json"),
            )
        )
        await session.commit()

    resp = await client.get(
        "/api/pricing/estimate/item?league=Dawn+of+the+Hunt&item_id=r1&tolerance_pct=10",
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "completed"
    assert body["result"]["chaos_equiv"] == 12.0


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


@pytest.mark.asyncio
async def test_apprise_enqueues_stash_backfill(app_stack) -> None:
    _app, client, mock_app = app_stack
    await _full_login(client, mock_app)
    csrf = client.cookies.get("poe2b_csrf")
    me = await client.get("/api/me")
    assert me.status_code == 200
    league = me.json().get("preferred_league") or "Fate of the Vaal"
    with patch("app.api.pricing.get_arq_pool", new_callable=AsyncMock) as mpool:
        mpool.return_value.enqueue_job = AsyncMock()
        resp = await client.post(
            f"/api/pricing/apprise?league={quote(league)}",
            headers={"X-CSRF-Token": csrf} if csrf else {},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json().get("ok") is True
        mpool.return_value.enqueue_job.assert_called_once()
        args = mpool.return_value.enqueue_job.call_args[0]
        assert args[0] == "backfill_item_price_estimates"
        assert args[3] is True
