"""Trade listing price parsing and median."""

from __future__ import annotations

from app.services.trade_listings import listing_chaos_value, median_chaos


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


def test_listing_divine_converted() -> None:
    row = {
        "listing": {
            "price": {"amount": 1, "currency": "divine", "type": "divine"},
        }
    }
    m = {"divine": 200.0, "divine orb": 200.0}
    assert listing_chaos_value(row, m) == 200.0
