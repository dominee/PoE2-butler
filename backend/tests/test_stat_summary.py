"""Cumulative equipment stat heuristics (templated mod lines + sections)."""

from __future__ import annotations

from app.domain.item import Item
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
