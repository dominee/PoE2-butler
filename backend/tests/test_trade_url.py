"""Unit tests for the trade-search payload + URL builder."""

from __future__ import annotations

import pytest

from app.domain.item import Item
from app.services.trade_url import (
    TRADE_BASE,
    build_exact_search,
    build_trade_url,
    build_upgrade_search,
    parse_mod_line,
)


def make_item(**overrides) -> Item:
    base = {
        "id": "i-1",
        "name": "Doom Horn",
        "type_line": "Spine Bow",
        "base_type": "Spine Bow",
        "rarity": "Rare",
        "ilvl": 82,
        "explicit_mods": [],
        "implicit_mods": [],
    }
    base.update(overrides)
    return Item(**base)


# --- parse_mod_line -----------------------------------------------------------


def test_parse_mod_line_single_number() -> None:
    parsed = parse_mod_line("+45 to maximum Life")
    assert parsed.values == [45.0]
    # The sign is captured as part of the numeric match and elided from the
    # template together with the digits.
    assert parsed.template == "# to maximum Life"
    assert parsed.is_percent is False


def test_parse_mod_line_percent() -> None:
    parsed = parse_mod_line("60% increased Physical Damage")
    assert parsed.values == [60.0]
    assert parsed.is_percent is True


def test_parse_mod_line_range_two_values() -> None:
    parsed = parse_mod_line("Adds 18 to 32 Physical Damage")
    assert parsed.values == [18.0, 32.0]
    assert parsed.template == "Adds # to # Physical Damage"


def test_parse_mod_line_negative_number() -> None:
    parsed = parse_mod_line("-5% to Cold Resistance")
    assert parsed.values == [-5.0]


def test_parse_mod_line_no_numbers() -> None:
    parsed = parse_mod_line("Trigger Socketed Spells when you Focus")
    assert parsed.values == []
    assert parsed.template == "Trigger Socketed Spells when you Focus"


# --- build_exact_search -------------------------------------------------------


def test_exact_search_uses_symmetric_window() -> None:
    item = make_item(explicit_mods=["+100 to maximum Life"])
    result = build_exact_search(item, tolerance_pct=10)
    assert result["mode"] == "exact"
    filters = result["payload"]["query"]["stats"][0]["filters"]
    assert filters[0]["value"] == {"min": 90, "max": 110}


def test_exact_search_floor_and_ceil() -> None:
    item = make_item(explicit_mods=["60% increased Physical Damage"])
    result = build_exact_search(item, tolerance_pct=10)
    f = result["payload"]["query"]["stats"][0]["filters"][0]
    # 60 * 0.9 = 54.0 (floor 54); 60 * 1.1 = 66.0 (ceil 66)
    assert f["value"] == {"min": 54, "max": 66}


def test_exact_search_non_numeric_mod_is_preserved_without_value() -> None:
    item = make_item(explicit_mods=["Trigger Socketed Spells when you Focus"])
    result = build_exact_search(item, tolerance_pct=10)
    filters = result["payload"]["query"]["stats"][0]["filters"]
    assert filters[0]["text"].startswith("Trigger")
    assert "value" not in filters[0]


def test_exact_search_tolerance_zero_pins_value() -> None:
    item = make_item(explicit_mods=["+100 to maximum Life"])
    result = build_exact_search(item, tolerance_pct=0)
    f = result["payload"]["query"]["stats"][0]["filters"][0]
    assert f["value"] == {"min": 100, "max": 100}


def test_exact_search_tolerance_100_doubles_window() -> None:
    item = make_item(explicit_mods=["+100 to maximum Life"])
    result = build_exact_search(item, tolerance_pct=100)
    f = result["payload"]["query"]["stats"][0]["filters"][0]
    # 100*(1-1)=0 (floor 0); 100*(1+1)=200 (ceil 200)
    assert f["value"] == {"min": 0, "max": 200}


def test_exact_search_two_value_mod_uses_average() -> None:
    item = make_item(explicit_mods=["Adds 18 to 32 Physical Damage"])
    result = build_exact_search(item, tolerance_pct=10)
    f = result["payload"]["query"]["stats"][0]["filters"][0]
    # mean(18,32)=25 ; 25*0.9=22.5 floor=22 ; 25*1.1=27.5 ceil=28
    assert f["value"] == {"min": 22, "max": 28}


def test_exact_search_negative_values_ordered_min_lte_max() -> None:
    item = make_item(explicit_mods=["-20% to Cold Resistance"])
    result = build_exact_search(item, tolerance_pct=10)
    f = result["payload"]["query"]["stats"][0]["filters"][0]
    # value -20, ±10% => (-22, -18); min/max should be (-22, -18).
    assert f["value"]["min"] == -22
    assert f["value"]["max"] == -18


def test_exact_search_covers_all_mod_buckets() -> None:
    item = make_item(
        implicit_mods=["+5 to all Attributes"],
        explicit_mods=["+45 to maximum Life"],
        rune_mods=["10% increased Attack Speed"],
        enchant_mods=["25% increased Skill Effect Duration"],
        crafted_mods=["+30% to Fire Resistance"],
    )
    result = build_exact_search(item, tolerance_pct=5)
    filters = result["payload"]["query"]["stats"][0]["filters"]
    buckets = {f["bucket"] for f in filters}
    assert buckets == {"implicit", "explicit", "rune", "enchant", "crafted"}


def test_exact_search_includes_type_and_rarity_filters() -> None:
    item = make_item()
    result = build_exact_search(item, tolerance_pct=10)
    type_filters = result["payload"]["query"]["filters"]["type_filters"]["filters"]
    assert type_filters["type"]["option"] == "Spine Bow"
    assert type_filters["rarity"]["option"] == "rare"


def test_exact_search_unique_item_omits_rarity_filter() -> None:
    item = make_item(rarity="Unique", base_type="Spine Bow")
    result = build_exact_search(item, tolerance_pct=10)
    type_filters = result["payload"]["query"]["filters"]["type_filters"]["filters"]
    assert "rarity" not in type_filters


def test_exact_search_rejects_negative_tolerance() -> None:
    with pytest.raises(ValueError):
        build_exact_search(make_item(), tolerance_pct=-1)


def test_exact_search_url_uses_league_segment() -> None:
    item = make_item()
    result = build_exact_search(item, tolerance_pct=10, league="Dawn of the Hunt")
    assert result["url"] == f"{TRADE_BASE}/Dawn%20of%20the%20Hunt"


# --- build_upgrade_search -----------------------------------------------------


def test_upgrade_uses_min_equal_to_floor_of_95pct() -> None:
    item = make_item(explicit_mods=["+100 to maximum Life"])
    result = build_upgrade_search(item, league="Std")
    f = result["payload"]["query"]["stats"][0]["filters"][0]
    # 100 * 0.95 = 95 (floor 95), no max.
    assert f["value"] == {"min": 95}
    assert "max" not in f["value"]


def test_upgrade_drops_non_numeric_mods() -> None:
    item = make_item(
        explicit_mods=[
            "+45 to maximum Life",
            "Trigger Socketed Spells when you Focus",
        ]
    )
    result = build_upgrade_search(item)
    filters = result["payload"]["query"]["stats"][0]["filters"]
    assert len(filters) == 1
    assert filters[0]["text"].startswith("+45")


def test_upgrade_two_value_mod_uses_average_for_min() -> None:
    item = make_item(explicit_mods=["Adds 18 to 32 Physical Damage"])
    result = build_upgrade_search(item)
    f = result["payload"]["query"]["stats"][0]["filters"][0]
    # average 25 * 0.95 = 23.75 -> floor 23
    assert f["value"] == {"min": 23}


def test_upgrade_keeps_base_type_filter() -> None:
    item = make_item()
    result = build_upgrade_search(item)
    type_filters = result["payload"]["query"]["filters"]["type_filters"]["filters"]
    assert type_filters["type"]["option"] == "Spine Bow"


# --- build_trade_url ----------------------------------------------------------


def test_build_trade_url_empty_league_returns_base() -> None:
    assert build_trade_url("") == TRADE_BASE


def test_build_trade_url_encodes_spaces() -> None:
    assert build_trade_url("Dawn of the Hunt") == f"{TRADE_BASE}/Dawn%20of%20the%20Hunt"
