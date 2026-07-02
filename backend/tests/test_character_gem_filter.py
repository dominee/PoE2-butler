"""Character gem filter parity with frontend characterGemFilter.ts."""

from __future__ import annotations

from app.domain.character_gem_filter import (
    is_notable_character_gem,
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
    assert is_notable_character_gem(item) is False
    assert should_include_character_item_in_apprise(item) is False


def test_shows_lineage_and_active_skill_gems() -> None:
    lineage = _gem(
        id="lineage",
        type_line="Rakiata's Flow",
        properties=[ItemProperty(name="Support, Lineage", value=None)],
    )
    skill = _gem(
        id="skill",
        type_line="Ice Nova",
        properties=[ItemProperty(name="Spell, AoE, Cold", value=None)],
    )
    assert is_notable_character_gem(lineage) is True
    assert is_notable_character_gem(skill) is True
    assert should_include_character_item_in_apprise(lineage) is True
    assert should_include_character_item_in_apprise(skill) is True


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
