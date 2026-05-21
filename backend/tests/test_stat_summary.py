"""Cumulative equipment stat heuristics (templated mod lines + sections)."""

from __future__ import annotations

import pytest

from app.domain.item import Item, ModDetail, ModMagnitude
from app.domain.stat_summary import summarize_equipment


def _by_section(s):
    return {sec.id: sec for sec in s.sections}


def test_life_and_spirit_from_mods() -> None:
    it = Item(
        id="1",
        explicit_mods=["+53 to maximum Life", "+5 to Spirit"],
    )
    out = summarize_equipment([it])
    m = _by_section(out)
    res = m["resources"]
    life = next(r for r in res.rows if "maximum Life" in r.label)
    assert life.values == [53.0]
    spirit = next(r for r in res.rows if "Spirit" in r.label)
    assert spirit.values == [5.0]


def test_strength_and_tri_res() -> None:
    it = Item(
        id="2",
        explicit_mods=["+20 to Strength", "+10% to all Elemental Resistances", "+2 to life"],
    )
    out = summarize_equipment([it])
    m = _by_section(out)
    st = m["attributes"].rows[0]
    assert st.values == [20.0]
    tri = next(r for r in m["resistances"].rows if "Elemental" in r.label)
    assert tri.values == [10.0]
    # "+2 to life" is not "maximum life" — typically lands in `other` or a loose bucket
    if "other" in m:
        assert any("life" in r.label.lower() for r in m["other"].rows)


def test_sum_same_template_across_two_items() -> None:
    a = Item(id="1", explicit_mods=["+10 to maximum Life"])
    b = Item(id="2", explicit_mods=["+10 to maximum Life"])
    out = summarize_equipment([a, b])
    m = _by_section(out)
    life = next(r for r in m["resources"].rows if "maximum Life" in r.label)
    assert life.values == [20.0]


def test_extra_lightning_damage_line() -> None:
    it = Item(
        id="x",
        explicit_mods=["Gain 10% of Elemental Damage as Extra Lightning Damage"],
    )
    out = summarize_equipment([it])
    m = _by_section(out)
    conv = m["conversion"]
    row = next(r for r in conv.rows if "Extra Lightning" in r.label)
    assert row.values == [10.0]


def test_range_adds_template_sums_mins_and_maxes() -> None:
    a = Item(id="1", explicit_mods=["Adds 5 to 12 Physical Damage to Attacks"])
    b = Item(id="2", explicit_mods=["Adds 5 to 12 Physical Damage to Attacks"])
    out = summarize_equipment([a, b])
    m = _by_section(out)
    dmg = m["damage"]
    row = next(r for r in dmg.rows if "Physical Damage" in r.label)
    assert row.values == [10.0, 24.0]


# ── quality_pct ───────────────────────────────────────────────────────────────

_T1_TIER = [
    {"tier_ggg": 1, "required_level": 1, "name": "of the Titan",
     "stats": [{"id": "life", "min": 70, "max": 80}]},
]


def _detail_with_all_tiers(t1_max: float) -> ModDetail:
    """Build a ModDetail with all_tiers that puts T1 max at *t1_max*."""
    return ModDetail(
        name="of the Titan",
        tier=1,
        magnitudes=[ModMagnitude(hash="h", min=None, max=None, t1_max=t1_max)],
        all_tiers=[
            {"tier_ggg": 1, "required_level": 1, "name": "of the Titan",
             "stats": [{"id": "life", "min": 60, "max": t1_max}]}
        ],
    )


def test_quality_pct_none_when_no_tier_data() -> None:
    """No all_tiers → quality_pct should be None for every section."""
    it = Item(id="q1", explicit_mods=["+50 to maximum Life"])
    out = summarize_equipment([it])
    m = _by_section(out)
    assert m["resources"].quality_pct is None


def test_quality_pct_at_t1_max() -> None:
    """When value == T1 max, quality_pct should be 100%."""
    it = Item(
        id="q2",
        explicit_mods=["+80 to maximum Life"],
        explicit_mod_details=[_detail_with_all_tiers(80.0)],
    )
    out = summarize_equipment([it])
    m = _by_section(out)
    assert m["resources"].quality_pct == pytest.approx(100.0, rel=0.01)


def test_quality_pct_below_t1() -> None:
    """When value < T1 max, quality_pct < 100."""
    it = Item(
        id="q3",
        explicit_mods=["+40 to maximum Life"],
        explicit_mod_details=[_detail_with_all_tiers(80.0)],
    )
    out = summarize_equipment([it])
    m = _by_section(out)
    # 40/80 = 50%
    assert m["resources"].quality_pct == pytest.approx(50.0, rel=0.01)


def test_quality_pct_overroll_above_100() -> None:
    """When value > T1 max (divine overroll), quality_pct > 100."""
    it = Item(
        id="q4",
        explicit_mods=["+88 to maximum Life"],
        explicit_mod_details=[_detail_with_all_tiers(80.0)],
    )
    out = summarize_equipment([it])
    m = _by_section(out)
    # 88/80 = 110%
    assert m["resources"].quality_pct == pytest.approx(110.0, rel=0.01)


def test_quality_pct_only_in_sections_with_tier_data() -> None:
    """A section with a mod that has tier data gets quality_pct; others stay None."""
    items = [
        Item(
            id="q5",
            explicit_mods=["+80 to maximum Life", "+20 to Strength"],
            explicit_mod_details=[_detail_with_all_tiers(80.0), ModDetail()],
        )
    ]
    out = summarize_equipment(items)
    m = _by_section(out)
    assert m["resources"].quality_pct is not None
    # Strength has no all_tiers data → attributes section quality_pct is None
    if "attributes" in m:
        assert m["attributes"].quality_pct is None
