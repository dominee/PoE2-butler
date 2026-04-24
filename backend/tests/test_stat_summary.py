"""Cumulative equipment stat heuristics."""

from __future__ import annotations

from app.domain.item import Item
from app.domain.stat_summary import summarize_equipment


def test_life_from_explicit() -> None:
    it = Item(
        id="1",
        explicit_mods=["+53 to maximum Life", "+5 to Spirit"],
    )
    out = summarize_equipment([it])
    assert out.get("life") == 53.0


def test_attributes_and_tri_res() -> None:
    it = Item(
        id="2",
        explicit_mods=["+20 to Strength", "+10% to all Elemental Resistances", "+2 to life"],
    )
    out = summarize_equipment([it])
    assert out.get("strength") == 20.0
    assert out.get("fire_res", 0) == 10.0
    assert out.get("cold_res", 0) == 10.0
