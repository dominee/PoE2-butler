"""Trade listing price parsing and median."""

from __future__ import annotations

import pytest

from app.config import Settings
from app.services import trade_listings as tl
from app.services.trade_listings import (
    estimate_upper_chaos_ceiling,
    filter_listing_chaos_samples,
    listing_chaos_value,
    listing_is_mirror_currency,
    median_chaos,
    median_chaos_robust,
    normalize_trade_chaos_map,
    trade_currency_chaos_fallback,
)


def test_median_odd_even() -> None:
    assert median_chaos([1, 2, 3, 4, 5]) == 3.0
    assert median_chaos([1, 2, 3, 4]) == 2.5


def test_median_robust_drops_upper_outlier_cluster() -> None:
    # Many low buyouts + two mirror-tier asks; robust median stays in the bulk.
    lows = [50.0, 52.0, 48.0, 55.0, 51.0]
    highs = [2_000_000.0, 2_100_000.0]
    assert median_chaos_robust(lows + highs) == median_chaos(lows)


def test_median_robust_small_sample_is_plain_median() -> None:
    assert median_chaos_robust([10.0, 20.0]) == 15.0


def test_median_robust_p90_trim_handles_sparse_extreme_outliers() -> None:
    # p90 trim helps when only a few ultra-high values sit above the bulk.
    lows = [50.0, 52.0, 48.0, 55.0, 51.0, 49.0, 53.0, 54.0]
    highs = [2_000_000.0, 2_100_000.0]
    med = median_chaos_robust(lows + highs)
    assert med == median_chaos(lows)


def test_listing_is_mirror_currency() -> None:
    row = {"listing": {"price": {"amount": 1, "currency": "mirror", "type": "mirror"}}}
    assert listing_is_mirror_currency(row)


def test_filter_listing_chaos_samples_drops_mirror_and_high_asks() -> None:
    s = Settings()
    chaos_map = trade_currency_chaos_fallback(s)
    cdiv = chaos_map["divine orb"]
    mirror_chaos = chaos_map["mirror"]
    samples: list[tuple[float, bool]] = []
    for _ in range(20):
        samples.append((450.0 * cdiv, False))
    for _ in range(5):
        samples.append((mirror_chaos, True))
    for _ in range(3):
        samples.append((6500.0 * cdiv, False))
    filtered = filter_listing_chaos_samples(samples, chaos_map, s)
    assert len(filtered) == 20
    assert max(filtered) <= estimate_upper_chaos_ceiling(
        [c for c, _ in samples if not _], chaos_map, s
    )
    assert median_chaos_robust(filtered) == pytest.approx(450.0 * cdiv, rel=0.02)


def test_filter_listing_chaos_samples_keeps_cheap_listings() -> None:
    s = Settings()
    chaos_map = trade_currency_chaos_fallback(s)
    cheap = [15.0, 20.0, 25.0, 30.0, 35.0]
    samples = [(c, False) for c in cheap]
    assert filter_listing_chaos_samples(samples, chaos_map, s) == cheap


def test_listing_chaos_chaos() -> None:
    row = {
        "listing": {
            "price": {"amount": 4, "currency": "chaos", "type": "chaos"},
        }
    }
    assert listing_chaos_value(row, {"divine orb": 200.0}) == 4.0


def test_listing_transmute_with_trade_fallback_map() -> None:
    row = {
        "listing": {
            "price": {"amount": 10, "currency": "transmute", "type": "~price"},
        }
    }
    s = Settings()
    m = trade_currency_chaos_fallback(s)
    v = listing_chaos_value(row, m)
    assert v is not None and v > 0


def test_listing_divine_converted() -> None:
    row = {
        "listing": {
            "price": {"amount": 1, "currency": "divine", "type": "divine"},
        }
    }
    m = {"divine": 200.0, "divine orb": 200.0}
    assert listing_chaos_value(row, m) == 200.0


def test_normalize_trade_chaos_map_syncs_divine_compact_id() -> None:
    s = Settings(trade_listing_divine_to_chaos=250.0)
    merged = trade_currency_chaos_fallback(s)
    merged["divine orb"] = 26.0
    assert merged["divine"] == 250.0
    norm = normalize_trade_chaos_map(merged, s)
    assert norm["divine"] == 26.0
    assert norm["divine orb"] == 26.0
    row = {
        "listing": {
            "price": {"amount": 500, "currency": "divine", "type": "divine"},
        }
    }
    assert listing_chaos_value(row, norm) == pytest.approx(500 * 26.0)


def test_normalize_prevents_po_e2_ten_x_display_inflation() -> None:
    """Regression: 500 div listing must not become ~4800 div via fallback 250 vs ninja 26."""
    s = Settings(trade_listing_divine_to_chaos=250.0)
    merged = trade_currency_chaos_fallback(s)
    merged.update({"divine orb": 26.0, "exalted orb": 26.0 / 185.0})
    norm = normalize_trade_chaos_map(merged, s)
    row = {
        "listing": {
            "price": {"amount": 500, "currency": "divine", "type": "divine"},
        }
    }
    chaos = listing_chaos_value(row, norm)
    assert chaos is not None
    assert chaos / norm["divine"] == pytest.approx(500.0, rel=1e-6)
    assert chaos / 250.0 == pytest.approx(52.0, rel=1e-6)  # wrong path would imply ~1250 div


def test_trade_listing_ids_from_search_post() -> None:
    ids, total = tl.trade_listing_ids_from_search_post(
        {"id": "x", "result": ["a", None, "b"], "total": 42}
    )
    assert ids == ["a", "b"]
    assert total == 42
    assert tl.trade_listing_ids_from_search_post(None) == ([], 0)


@pytest.mark.asyncio
async def test_trade_search_collect_string_ids_skips_null_only_pages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[int] = []

    async def fake_list(
        settings: Settings,
        league: str,
        sid: str,
        *,
        start: int = 0,
        redis=None,
    ) -> tuple[int, list[str], bool, int]:
        calls.append(start)
        if start == 0:
            return 42, [], False, 10
        if start == 10:
            return 42, ["id_a", "id_b"], False, 10
        return 42, [], False, 10

    monkeypatch.setattr(tl, "trade_search_list_result", fake_list)
    s = Settings()
    total, ids, rl = await tl.trade_search_collect_string_ids(s, "L", "sid", redis=None)
    assert not rl
    assert total == 42
    assert ids == ["id_a", "id_b"]
    assert calls == [0, 10]
