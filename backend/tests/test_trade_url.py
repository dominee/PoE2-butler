"""Unit tests for the trade-search payload + URL builder."""

from __future__ import annotations

import pytest

from app.domain.item import Item
from app.domain.item import ModDetail, ModMagnitude
from app.services.trade_url import (
    TRADE_BASE,
    _tier_weight,
    build_exact_search,
    build_trade_url,
    build_trade_url_with_search_id,
    build_upgrade_search,
    build_weighted_upgrade_search,
    fix_weight_group_floor,
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
    q = result["payload"]["query"]
    assert q["type"] == "Spine Bow"
    assert q["status"]["option"] == "securable"
    f = q["filters"]
    assert "status_filters" not in f
    assert "trade_filters" not in f
    tf = f["type_filters"]
    assert tf["disabled"] is False
    assert tf["filters"]["rarity"]["option"] == "rare"


def test_exact_search_unique_sets_name_type_and_rarity() -> None:
    item = make_item(
        rarity="Unique",
        name="Headhunter",
        base_type="Heavy Belt",
    )
    result = build_exact_search(item, tolerance_pct=10)
    q = result["payload"]["query"]
    assert q["type"] == "Heavy Belt"
    assert q["name"] == "Headhunter"
    assert q["status"]["option"] == "securable"
    f = q["filters"]
    assert "status_filters" not in f
    assert "trade_filters" not in f
    tf = f["type_filters"]
    assert tf["disabled"] is False
    assert tf["filters"]["rarity"]["option"] == "unique"


def test_exact_search_unique_without_display_name_omits_query_name() -> None:
    """GGG still needs ``name`` for a specific unique; omit key when unknown."""
    item = make_item(rarity="Unique", base_type="Spine Bow", name="")
    result = build_exact_search(item, tolerance_pct=10)
    q = result["payload"]["query"]
    assert q["type"] == "Spine Bow"
    assert "name" not in q
    assert q["filters"]["type_filters"]["filters"]["rarity"]["option"] == "unique"


def test_exact_search_currency_item_omits_rarity_filter() -> None:
    item = make_item(rarity="Currency", base_type="Chaos Orb")
    result = build_exact_search(item, tolerance_pct=10)
    q = result["payload"]["query"]
    assert q["type"] == "Chaos Orb"
    assert q["status"]["option"] == "securable"
    f = q["filters"]
    assert "type_filters" not in f


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
    q = result["payload"]["query"]
    assert q["type"] == "Spine Bow"
    assert q["status"]["option"] == "securable"
    f = q["filters"]
    assert "status_filters" not in f
    assert "trade_filters" not in f
    tf = f["type_filters"]
    assert tf["disabled"] is False
    assert tf["filters"]["rarity"]["option"] == "rare"


# --- build_trade_url ----------------------------------------------------------


def test_build_trade_url_empty_league_returns_base() -> None:
    assert build_trade_url("") == TRADE_BASE


def test_build_trade_url_encodes_spaces() -> None:
    assert build_trade_url("Dawn of the Hunt") == f"{TRADE_BASE}/Dawn%20of%20the%20Hunt"


def test_build_trade_url_with_search_id_appends_segment() -> None:
    assert (
        build_trade_url_with_search_id("Dawn of the Hunt", "Ab12cd")
        == f"{TRADE_BASE}/Dawn%20of%20the%20Hunt/Ab12cd"
    )


def test_build_trade_url_with_search_id_empty_id_returns_league_url() -> None:
    assert build_trade_url_with_search_id("Std", "") == f"{TRADE_BASE}/Std"


def test_explicit_life_mod_uses_poe2_explicit_stat_id() -> None:
    item = make_item(explicit_mods=["+100 to maximum Life"])
    result = build_exact_search(item, tolerance_pct=10)
    f = result["payload"]["query"]["stats"][0]["filters"][0]
    assert f["id"] == "explicit.stat_3299347043"


def test_implicit_life_mod_uses_implicit_stat_id() -> None:
    item = make_item(implicit_mods=["+50 to maximum Life"])
    result = build_exact_search(item, tolerance_pct=10)
    f = result["payload"]["query"]["stats"][0]["filters"][0]
    assert f["id"] == "implicit.stat_3299347043"


# --- _tier_weight -------------------------------------------------------------


def test_tier_weight_t1_is_30() -> None:
    assert _tier_weight(1) == 30


def test_tier_weight_t2_is_20() -> None:
    assert _tier_weight(2) == 20


def test_tier_weight_t3_is_15() -> None:
    assert _tier_weight(3) == 15


def test_tier_weight_t4_is_default() -> None:
    assert _tier_weight(4) == 10


def test_tier_weight_none_is_default() -> None:
    assert _tier_weight(None) == 10


def test_tier_weight_high_tier_is_default() -> None:
    assert _tier_weight(10) == 10


# --- build_weighted_upgrade_search --------------------------------------------


def _make_detail(tier: int | None, t1_max: float | None = None) -> ModDetail:
    return ModDetail(
        name="",
        tier=tier,
        level=None,
        magnitudes=[ModMagnitude(hash="h", min=None, max=None, t1_max=t1_max)],
    )


def test_weighted_upgrade_mode_and_type() -> None:
    item = make_item(explicit_mods=["+100 to maximum Life"])
    result = build_weighted_upgrade_search(item, league="Std")
    assert result["mode"] == "weighted_upgrade"
    assert result["league"] == "Std"
    assert result["url"].startswith(TRADE_BASE)


def test_weighted_upgrade_uses_weight_stats_group() -> None:
    item = make_item(explicit_mods=["+100 to maximum Life"])
    result = build_weighted_upgrade_search(item)
    stats = result["payload"]["query"].get("stats", [])
    assert len(stats) == 1
    assert stats[0]["type"] == "weight"
    assert "value" in stats[0]
    assert "min" in stats[0]["value"]


def test_weighted_upgrade_t1_mod_gets_weight_30() -> None:
    """A T1 mod detail should produce weight=30 in the filter."""
    detail = _make_detail(tier=1)
    item = make_item(
        explicit_mods=["+100 to maximum Life"],
        explicit_mod_details=[detail],
    )
    result = build_weighted_upgrade_search(item)
    filters = result["payload"]["query"]["stats"][0]["filters"]
    assert len(filters) == 1
    assert filters[0]["value"]["weight"] == 30


def test_weighted_upgrade_t2_mod_gets_weight_20() -> None:
    detail = _make_detail(tier=2)
    item = make_item(
        explicit_mods=["+100 to maximum Life"],
        explicit_mod_details=[detail],
    )
    result = build_weighted_upgrade_search(item)
    filters = result["payload"]["query"]["stats"][0]["filters"]
    assert filters[0]["value"]["weight"] == 20


def test_weighted_upgrade_unknown_tier_gets_default_weight() -> None:
    detail = _make_detail(tier=None)
    item = make_item(
        explicit_mods=["+100 to maximum Life"],
        explicit_mod_details=[detail],
    )
    result = build_weighted_upgrade_search(item)
    filters = result["payload"]["query"]["stats"][0]["filters"]
    assert filters[0]["value"]["weight"] == 10


def test_weighted_upgrade_floor_is_85pct_of_weighted_sum() -> None:
    """floor( 100 * 30 * 0.85 ) = floor(2550) = 2550."""
    detail = _make_detail(tier=1)
    item = make_item(
        explicit_mods=["+100 to maximum Life"],
        explicit_mod_details=[detail],
    )
    result = build_weighted_upgrade_search(item)
    floor_val = result["payload"]["query"]["stats"][0]["value"]["min"]
    assert floor_val == 2550  # 100 * 30 * 0.85 = 2550


def test_weighted_upgrade_multiple_mods_sum_correctly() -> None:
    """T1 explicit life (+100) and T2 implicit life (+20) — both have bundled stat ids.

    ``+20 to maximum Life`` (implicit, T2) → weight 20, contribution 20*20 = 400.
    ``+100 to maximum Life`` (explicit, T1) → weight 30, contribution 100*30 = 3000.
    Weighted sum = 3400. Floor = floor(3400 * 0.85) = 2890.
    """
    item = make_item(
        implicit_mods=["+20 to maximum Life"],
        implicit_mod_details=[_make_detail(tier=2)],
        explicit_mods=["+100 to maximum Life"],
        explicit_mod_details=[_make_detail(tier=1)],
    )
    result = build_weighted_upgrade_search(item)
    # Initial floor includes both mods (both have bundled ids → _bxw set)
    floor_val = result["payload"]["query"]["stats"][0]["value"]["min"]
    assert floor_val == 2890


def test_weighted_upgrade_drops_non_numeric_mods() -> None:
    item = make_item(
        explicit_mods=["+100 to maximum Life", "Trigger Socketed Spells when you Focus"]
    )
    result = build_weighted_upgrade_search(item)
    stats = result["payload"]["query"].get("stats", [])
    if stats:
        # "Trigger" has no numeric value so it cannot appear as a weight filter
        filter_texts = [f.get("text", "") for f in stats[0]["filters"]]
        assert not any("Trigger" in t for t in filter_texts)


def test_weighted_upgrade_unknown_mod_included_without_id() -> None:
    """A mod with no bundled stat id is included in the filter (for enrichment) but has no id.

    The stats group IS present — enrichment fills ids from the live index; only
    after enrichment does ggg_search_body_from_result_payload drop id-less entries.
    """
    item = make_item(explicit_mods=["+999 to Fictional Attribute That Is Not In Catalog"])
    result = build_weighted_upgrade_search(item)
    stats = result["payload"]["query"].get("stats", [])
    # Stats group exists with one filter entry (no id yet, pending enrichment)
    assert len(stats) == 1
    assert stats[0]["type"] == "weight"
    assert len(stats[0]["filters"]) == 1
    assert "id" not in stats[0]["filters"][0]


def test_fix_weight_group_floor_recomputes_from_id_bearing_filters() -> None:
    """floor is recalculated after enrichment using only id-bearing entries."""
    item = make_item(
        explicit_mods=["+100 to maximum Life"],
        explicit_mod_details=[_make_detail(tier=1)],
    )
    result = build_weighted_upgrade_search(item)
    # Simulate enrichment filling the id on the filter
    filters = result["payload"]["query"]["stats"][0]["filters"]
    assert len(filters) == 1
    filters[0]["id"] = "explicit.stat_3299347043"  # already set, but make explicit
    fix_weight_group_floor(result["payload"])
    floor_val = result["payload"]["query"]["stats"][0]["value"]["min"]
    # 100 * 30 * 0.85 = 2550
    assert floor_val == 2550


def test_fix_weight_group_floor_ignores_filters_without_id() -> None:
    """Filters without id after enrichment are excluded from the floor sum."""
    item = make_item(
        explicit_mods=["+100 to maximum Life", "+50 to Fictional Stat"],
        explicit_mod_details=[_make_detail(tier=1), _make_detail(tier=2)],
    )
    result = build_weighted_upgrade_search(item)
    stats = result["payload"]["query"]["stats"][0]
    # Only give id to the life filter
    for f in stats["filters"]:
        if "maximum Life" in f.get("text", ""):
            f["id"] = "explicit.stat_3299347043"
        else:
            f.pop("id", None)  # ensure no id on the fictional stat
    fix_weight_group_floor(result["payload"])
    floor_val = stats["value"]["min"]
    # Only life contributes: 100 * 30 * 0.85 = 2550
    assert floor_val == 2550


def test_weighted_upgrade_keeps_base_type_and_rarity() -> None:
    item = make_item()
    result = build_weighted_upgrade_search(item)
    q = result["payload"]["query"]
    assert q["type"] == "Spine Bow"
    assert q["status"]["option"] == "securable"
    assert q["filters"]["type_filters"]["filters"]["rarity"]["option"] == "rare"
