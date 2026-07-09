"""Trade-tier price estimate validation (Mageblood / mirror-outlier scenarios)."""

from __future__ import annotations

import pytest

from app.config import Settings
from app.domain.item import Item, parse_item
from app.services.pricing.estimate_engine import build_chaos_currency_map
from app.services.trade_listings import (
    filter_listing_chaos_samples,
    median_chaos_robust,
    trade_currency_chaos_fallback,
)
from app.services.trade_url import build_exact_search


def test_parse_item_reads_double_corrupted() -> None:
    raw = {
        "id": "mb-1",
        "name": "Mageblood",
        "typeLine": "Heavy Belt",
        "baseType": "Heavy Belt",
        "rarity": "Unique",
        "corrupted": False,
        "doubleCorrupted": True,
    }
    item = parse_item(raw)
    assert item.corrupted is False
    assert item.double_corrupted is True


def test_mageblood_trade_query_pins_uncorrupted_state() -> None:
    item = Item(
        id="mb-1",
        name="Mageblood",
        type_line="Heavy Belt",
        base_type="Heavy Belt",
        rarity="Unique",
        corrupted=False,
        double_corrupted=False,
    )
    q = build_exact_search(item, tolerance_pct=10, league="Fate of the Vaal")["payload"]["query"]
    mf = q["filters"]["misc_filters"]["filters"]
    assert q["name"] == "Mageblood"
    assert mf["corrupted"]["option"] == "false"
    assert mf["twice_corrupted"]["option"] == "false"


def test_mageblood_median_rejects_mirror_outliers() -> None:
    """Regression: inflated ~12k div estimates from mirror-tier asks in the sample."""
    s = Settings()
    chaos_map = trade_currency_chaos_fallback(s)
    cdiv = chaos_map["divine orb"]
    mirror_chaos = chaos_map["mirror"]
    samples: list[tuple[float, bool]] = []
    for div in (399.0, 420.0, 450.0, 480.0, 500.0, 510.0, 520.0, 530.0):
        samples.append((div * cdiv, False))
    for _ in range(6):
        samples.append((mirror_chaos, True))
    for div in (6500.0, 6500.0, 6500.0):
        samples.append((div * cdiv, False))
    filtered = filter_listing_chaos_samples(samples, chaos_map, s)
    med_div = median_chaos_robust(filtered) / cdiv
    assert 350.0 <= med_div <= 600.0


@pytest.mark.asyncio
async def test_build_chaos_currency_map_normalizes_divine_compact_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_map(_league: str) -> dict[str, float]:
        return {"chaos orb": 1.0, "divine orb": 26.0, "exalted orb": 26.0 / 185.0}

    class FakePoe:
        async def currency_chaos_map(self, league: str) -> dict[str, float]:
            return await fake_map(league)

        async def aclose(self) -> None:
            return None

    monkeypatch.setattr(
        "app.services.pricing.estimate_engine._poe_ninja_from_settings",
        lambda _s: FakePoe(),
    )
    s = Settings(pricing_source="poe_ninja", trade_listing_divine_to_chaos=250.0)
    m = await build_chaos_currency_map(s, "Fate of the Vaal")
    assert m["divine"] == 26.0
    assert m["divine orb"] == 26.0
