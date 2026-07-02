"""Tests for the pricing subsystem."""

from __future__ import annotations

import httpx
import pytest
from fakeredis.aioredis import FakeRedis

from app.config import Settings
from app.domain.item import Item, ItemProperty
from app.services.pricing.cache import PriceCache
from app.services.pricing.currency_rates import resolve_currency_rates
from app.services.pricing.matcher import match_item
from app.services.pricing.poe_ninja import PoeNinjaSource, normalize_poe2_exchange_overview
from app.services.pricing.service import PricingService
from app.services.pricing.source import PriceEstimate, PriceUnit
from app.services.pricing.static import StaticPriceSource


def test_normalize_poe2_exchange_overview_chaos_equivalents() -> None:
    raw = {
        "core": {"rates": {"chaos": 26.0, "exalted": 185.0}},
        "items": [
            {"id": "divine", "name": "Divine Orb"},
            {"id": "exalted", "name": "Exalted Orb"},
            {"id": "chaos", "name": "Chaos Orb"},
        ],
        "lines": [
            {"id": "divine", "primaryValue": 1.0},
            {"id": "exalted", "primaryValue": 1.0 / 185.0},
            {"id": "chaos", "primaryValue": 1.0 / 26.0},
        ],
    }
    out = normalize_poe2_exchange_overview(raw)
    lines = {
        str(x.get("currencyTypeName")): float(x.get("chaosEquivalent", 0))
        for x in out["lines"]
    }
    assert abs(lines["Chaos Orb"] - 1.0) < 1e-9
    assert abs(lines["Divine Orb"] - 26.0) < 1e-9
    assert abs(lines["Exalted Orb"] - (26.0 / 185.0)) < 1e-9


@pytest.mark.asyncio
async def test_poe_ninja_poe2_currency_chaos_map_via_mock_transport() -> None:
    index_state = {
        "economyLeagues": [
            {"name": "Fate of the Vaal", "url": "vaal", "displayName": "Fate of the Vaal"},
        ],
        "oldEconomyLeagues": [],
    }
    overview = {
        "core": {"rates": {"chaos": 26.0, "exalted": 185.0}},
        "items": [
            {"id": "divine", "name": "Divine Orb"},
            {"id": "exalted", "name": "Exalted Orb"},
            {"id": "chaos", "name": "Chaos Orb"},
        ],
        "lines": [
            {"id": "divine", "primaryValue": 1.0},
            {"id": "exalted", "primaryValue": 1.0 / 185.0},
            {"id": "chaos", "primaryValue": 1.0 / 26.0},
        ],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/poe2/api/data/index-state"):
            return httpx.Response(200, json=index_state)
        if path.endswith("/poe2/api/economy/exchange/current/overview"):
            return httpx.Response(200, json=overview)
        return httpx.Response(404, json={})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        src = PoeNinjaSource("https://poe.ninja", client=client)
        try:
            m = await src.currency_chaos_map("vaal")
        finally:
            await src.aclose()
    assert abs(m["chaos orb"] - 1.0) < 1e-9
    assert abs(m["divine orb"] - 26.0) < 1e-9
    assert abs(m["exalted orb"] - (26.0 / 185.0)) < 1e-9


@pytest.mark.asyncio
async def test_poe_ninja_poe1_base_url_falls_back_to_poe2_on_currencyoverview_404() -> None:
    """Legacy PRICING_BASE_URL=…/api/data must still load PoE2 leagues (PoE1 endpoint 404s)."""
    index_state = {
        "economyLeagues": [
            {"name": "Fate of the Vaal", "url": "vaal", "displayName": "Fate of the Vaal"},
        ],
        "oldEconomyLeagues": [],
    }
    overview = {
        "core": {"rates": {"chaos": 26.0, "exalted": 185.0}},
        "items": [
            {"id": "divine", "name": "Divine Orb"},
            {"id": "exalted", "name": "Exalted Orb"},
            {"id": "chaos", "name": "Chaos Orb"},
        ],
        "lines": [
            {"id": "divine", "primaryValue": 1.0},
            {"id": "exalted", "primaryValue": 1.0 / 185.0},
            {"id": "chaos", "primaryValue": 1.0 / 26.0},
        ],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/currencyoverview"):
            return httpx.Response(404, json={})
        if path.endswith("/poe2/api/data/index-state"):
            return httpx.Response(200, json=index_state)
        if path.endswith("/poe2/api/economy/exchange/current/overview"):
            return httpx.Response(200, json=overview)
        return httpx.Response(404, json={})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        src = PoeNinjaSource("https://poe.ninja/api/data", client=client)
        try:
            m = await src.currency_chaos_map("Fate of the Vaal")
        finally:
            await src.aclose()
    assert abs(m["divine orb"] - 26.0) < 1e-9
    assert abs(m["exalted orb"] - (26.0 / 185.0)) < 1e-9


@pytest.mark.asyncio
async def test_resolve_currency_rates_static_fallback_ex_per_div() -> None:
    s = Settings(
        pricing_source="static",
        trade_listing_divine_to_chaos=250,
        trade_listing_exalt_to_chaos=10,
    )
    r = await resolve_currency_rates(s, "Dawn of the Hunt")
    assert r["chaos_per_divine"] == 250.0
    assert r["chaos_per_exalted"] == 10.0
    assert r["exalted_per_divine"] == 25.0
    assert r["source"] == "config_fallback"


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


def test_match_item_lineage_gem() -> None:
    key = match_item(
        _item(
            rarity="Gem",
            type_line="Rakiata's Flow",
            base_type="Rakiata's Flow",
            properties=[{"name": "[SupportGem|Support], [LineageSupports|Lineage]", "value": None}],
        )
    )
    assert key.category == "lineage_gem"
    assert key.name == "Rakiata's Flow"


def test_match_item_skill_gem_uses_uncut_level() -> None:
    key = match_item(
        _item(
            rarity="Gem",
            type_line="Malice",
            base_type="Malice",
            properties=[ItemProperty(name="Level", value="18")],
        )
    )
    assert key.category == "skill_gem"
    assert key.gem_level == 18


def test_match_item_corrupted_gem_uses_trade() -> None:
    key = match_item(
        _item(
            rarity="Gem",
            type_line="Ice Nova",
            corrupted=True,
            properties=[ItemProperty(name="Level", value="21")],
        )
    )
    assert key.category == "gem_trade"
    assert key.gem_level == 21


def test_match_item_unique_charm_and_flask() -> None:
    charm = match_item(
        _item(
            rarity="Unique",
            name="Arakaali's Gift",
            base_type="Antidote Charm",
        )
    )
    assert charm.category == "unique_charm"
    flask = match_item(
        _item(
            rarity="Unique",
            name="Olroth's Resolve",
            type_line="Olroth's Resolve",
            base_type="Ultimate Life Flask",
        )
    )
    assert flask.category == "unique_flask"


@pytest.mark.asyncio
async def test_poe_ninja_lineage_and_uncut_gem_lookup() -> None:
    overview_lineage = {
        "core": {"rates": {"chaos": 8.0}},
        "items": [{"id": "rakiatas-flow", "name": "Rakiata's Flow"}],
        "lines": [{"id": "rakiatas-flow", "primaryValue": 10.0}],
    }
    overview_uncut = {
        "core": {"rates": {"chaos": 8.0}},
        "items": [{"id": "uncut-skill-gem-18", "name": "Uncut Skill Gem (Level 18)"}],
        "lines": [{"id": "uncut-skill-gem-18", "primaryValue": 0.5}],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/poe2/api/data/index-state"):
            return httpx.Response(
                200,
                json={"economyLeagues": [{"name": "Runes of Aldur", "url": "runesofaldur"}]},
            )
        if path.endswith("/poe2/api/economy/exchange/current/overview"):
            t = request.url.params.get("type")
            if t == "LineageSupportGems":
                return httpx.Response(200, json=overview_lineage)
            if t == "UncutGems":
                return httpx.Response(200, json=overview_uncut)
        return httpx.Response(404, json={})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        src = PoeNinjaSource("https://poe.ninja", client=client)
        try:
            from app.services.pricing.matcher import ItemKey

            lineage = await src.lookup(
                "Runes of Aldur",
                ItemKey(category="lineage_gem", base_type="Rakiata's Flow", name="Rakiata's Flow"),
            )
            uncut = await src.lookup(
                "Runes of Aldur",
                ItemKey(category="skill_gem", base_type="Malice", gem_level=18),
            )
        finally:
            await src.aclose()
    assert lineage is not None
    assert abs(lineage.chaos_equiv - 80.0) < 1e-9
    assert uncut is not None
    assert abs(uncut.chaos_equiv - 4.0) < 1e-9


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
