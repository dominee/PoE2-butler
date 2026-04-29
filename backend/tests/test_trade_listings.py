"""Trade listing price parsing and median."""

from __future__ import annotations

import pytest

from app.config import Settings
from app.services import trade_listings as tl
from app.services.trade_listings import (
    listing_chaos_value,
    median_chaos,
    trade_currency_chaos_fallback,
)


def test_median_odd_even() -> None:
    assert median_chaos([1, 2, 3, 4, 5]) == 3.0
    assert median_chaos([1, 2, 3, 4]) == 2.5


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


def test_trade_listing_ids_from_search_post() -> None:
    ids, total = tl.trade_listing_ids_from_search_post(
        {"id": "x", "result": ["a", None, "b"], "total": 42}
    )
    assert ids == ["a", "b"]
    assert total == 42
    assert tl.trade_listing_ids_from_search_post(None) == ([], 0)


@pytest.mark.asyncio
async def test_trade_search_collect_string_ids_skips_null_only_pages(monkeypatch: pytest.MonkeyPatch) -> None:
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
