"""Character gem filter parity with frontend characterGemFilter.ts."""

from __future__ import annotations

from app.domain.character_gem_filter import (
    is_character_skill_gem,
    is_displayed_in_skill_gems_section,
    is_lineage_support,
    is_notable_character_gem,
    should_include_character_gem_in_pricing,
    should_include_character_item_in_apprise,
)
from app.domain.item import Item, ItemProperty


def _gem(**kwargs: object) -> Item:
    defaults: dict = {
        "id": "g1",
        "inventory_id": "SkillSlots",
        "w": 1,
        "h": 1,
        "type_line": "Gem",
        "base_type": "Gem",
        "rarity": "Gem",
        "properties": [],
    }
    defaults.update(kwargs)
    return Item(**defaults)


def test_hides_tiered_generic_supports() -> None:
    item = _gem(
        id="rapid",
        type_line="Rapid Attacks II",
        base_type="Rapid Attacks II",
        properties=[ItemProperty(name="[SupportGem|Support]", value=None)],
    )
    assert is_character_skill_gem(item) is False
    assert is_displayed_in_skill_gems_section(item) is False
    assert should_include_character_gem_in_pricing(item) is False
    assert should_include_character_item_in_apprise(item) is False


def test_lineage_in_display_and_pricing_not_skill_gem() -> None:
    lineage = _gem(
        id="lineage",
        type_line="Rakiata's Flow",
        properties=[ItemProperty(name="Support, Lineage", value=None)],
    )
    assert is_lineage_support(lineage) is True
    assert is_character_skill_gem(lineage) is False
    assert is_displayed_in_skill_gems_section(lineage) is True
    assert should_include_character_gem_in_pricing(lineage) is True
    assert should_include_character_item_in_apprise(lineage) is True


def test_active_skill_gem_displayed_not_priced() -> None:
    skill = _gem(
        id="skill",
        type_line="Ice Nova",
        properties=[ItemProperty(name="Spell, AoE, Cold", value=None)],
    )
    assert is_character_skill_gem(skill) is True
    assert is_displayed_in_skill_gems_section(skill) is True
    assert should_include_character_gem_in_pricing(skill) is False
    assert should_include_character_item_in_apprise(skill) is False


def test_ascendancy_skill_displayed_not_priced() -> None:
    ascendancy = _gem(
        id="asc",
        type_line="Ascendancy Skill",
        inventory_id="AscendancySkills",
    )
    assert is_character_skill_gem(ascendancy) is True
    assert should_include_character_gem_in_pricing(ascendancy) is False
    assert should_include_character_item_in_apprise(ascendancy) is False


def test_includes_equipped_gear() -> None:
    bow = Item(
        id="w1",
        inventory_id="Weapon",
        w=2,
        h=4,
        type_line="Spine Bow",
        base_type="Spine Bow",
        rarity="Rare",
    )
    assert should_include_character_item_in_apprise(bow) is True


def test_notable_aliases_display() -> None:
    skill = _gem(id="skill", type_line="Ice Nova")
    assert is_notable_character_gem(skill) is is_displayed_in_skill_gems_section(skill)
