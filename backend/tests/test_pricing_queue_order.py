"""Bulk price lookup processes rarities in a fixed order (uniques first)."""

from __future__ import annotations

from app.domain.item import Item
from app.services.pricing.service import _items_sorted_for_price_queue


def _item(iid: str, rarity: str) -> Item:
    return Item.model_validate({"id": iid, "rarity": rarity, "name": "X"})


def test_price_queue_sorts_currency_first() -> None:
    items = [
        _item("a", "Normal"),
        _item("b", "Unique"),
        _item("c", "Currency"),
        _item("d", "Rare"),
    ]
    out = _items_sorted_for_price_queue(items)
    assert [x.id for x in out] == ["c", "b", "d", "a"]


def test_price_queue_tiebreaks_by_id() -> None:
    items = [_item("m", "Unique"), _item("k", "Unique")]
    out = _items_sorted_for_price_queue(items)
    assert [x.id for x in out] == ["k", "m"]
