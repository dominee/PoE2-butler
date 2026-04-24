"""Tests for the pricing subsystem."""

from __future__ import annotations

import pytest
from fakeredis.aioredis import FakeRedis

from app.domain.item import Item
from app.services.pricing.cache import PriceCache
from app.services.pricing.matcher import match_item
from app.services.pricing.service import PricingService
from app.services.pricing.source import PriceEstimate, PriceUnit
from app.services.pricing.static import StaticPriceSource


def _item(**kwargs) -> Item:
    defaults: dict = {
        "id": "i",
        "inventory_id": "Stash1",
        "w": 1,
        "h": 1,
        "x": 0,
        "y": 0,
        "name": "",
        "type_line": "",
        "base_type": "",
        "rarity": "Normal",
        "ilvl": None,
        "identified": True,
        "corrupted": False,
        "properties": [],
        "requirements": [],
        "implicit_mods": [],
        "explicit_mods": [],
        "rune_mods": [],
        "enchant_mods": [],
        "crafted_mods": [],
        "sockets": [],
        "stack_size": None,
        "max_stack_size": None,
        "icon": None,
    }
    defaults.update(kwargs)
    return Item(**defaults)


def test_match_item_currency_uses_type_line() -> None:
    key = match_item(_item(type_line="Divine Orb", rarity="Currency"))
    assert key.category == "currency"
    assert key.base_type == "Divine Orb"


def test_match_item_unique_uses_name() -> None:
    key = match_item(_item(rarity="Unique", name="Headhunter", base_type="Leather Belt"))
    assert key.category == "unique"
    assert key.name == "Headhunter"


@pytest.mark.asyncio
async def test_static_source_prices_divine_and_caches() -> None:
    redis = FakeRedis(decode_responses=True)
    source = StaticPriceSource()
    cache = PriceCache(redis)
    svc = PricingService(source, cache)
    item = _item(type_line="Divine Orb", rarity="Currency")

    first = await svc.price_for("Dawn of the Hunt", item)
    assert first is not None
    assert first.unit == PriceUnit.CHAOS
    assert first.chaos_equiv == 180.0

    # The second call should hit the Redis cache; mutate the source to prove it.
    source._catalogue = {"currency": {}}  # type: ignore[attr-defined]
    cached = await svc.price_for("Dawn of the Hunt", item)
    assert cached is not None
    assert cached.chaos_equiv == 180.0


@pytest.mark.asyncio
async def test_static_source_returns_none_for_unknown_and_negative_caches() -> None:
    redis = FakeRedis(decode_responses=True)
    source = StaticPriceSource()
    cache = PriceCache(redis)
    svc = PricingService(source, cache)
    item = _item(type_line="Nothing Orb", rarity="Currency")

    assert await svc.price_for("Dawn of the Hunt", item) is None
    # Even if the source would now answer, we cached the miss for a short while.
    source._catalogue["currency"]["nothing orb"] = 5.0  # type: ignore[index]
    assert await svc.price_for("Dawn of the Hunt", item) is None


@pytest.mark.asyncio
async def test_bulk_pricing_returns_per_item_results() -> None:
    redis = FakeRedis(decode_responses=True)
    source = StaticPriceSource()
    cache = PriceCache(redis)
    svc = PricingService(source, cache)

    items = [
        _item(id="a", type_line="Chaos Orb", rarity="Currency"),
        _item(id="b", type_line="Mystery Flask", rarity="Normal"),
        _item(id="c", rarity="Unique", name="Headhunter", base_type="Leather Belt"),
    ]
    result = await svc.price_bulk("Dawn of the Hunt", items)
    assert set(result.keys()) == {"a", "b", "c"}
    assert result["a"] is not None and result["a"].chaos_equiv == 1.0
    assert result["b"] is None
    assert result["c"] is not None and result["c"].chaos_equiv == 2500.0


def test_price_estimate_round_trip_json() -> None:
    est = PriceEstimate(value=3.0, chaos_equiv=3.0, source="static")
    blob = est.model_dump_json()
    PriceEstimate.model_validate_json(blob)
