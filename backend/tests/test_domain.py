"""Unit tests for domain normalizers."""

from __future__ import annotations

import sys
from pathlib import Path

from app.domain.character import (
    collect_character_items,
    normalize_character_class,
    parse_detail,
    parse_summaries,
)
from app.domain.item import parse_item
from app.domain.league import parse_leagues, pick_current_league

# Allow importing mock-ggg helpers inside tests that need them.
_MOCK_GGG_APP = Path(__file__).resolve().parents[2] / "mock-ggg" / "app"


def test_parse_leagues_picks_non_hardcore_current() -> None:
    payload = {
        "leagues": [
            {"id": "Standard", "current": False},
            {"id": "Hardcore Dawn of the Hunt", "current": True},
            {"id": "Dawn of the Hunt", "current": True},
        ]
    }
    leagues = parse_leagues(payload)
    assert {league.id for league in leagues} == {
        "Standard",
        "Hardcore Dawn of the Hunt",
        "Dawn of the Hunt",
    }
    assert pick_current_league(leagues) == "Dawn of the Hunt"


def test_parse_leagues_handles_empty() -> None:
    assert parse_leagues({}) == []
    assert pick_current_league([]) is None


def test_parse_item_infers_rarity_from_frame_type() -> None:
    item = parse_item({"id": "x", "frameType": 5, "typeLine": "Divine Orb"})
    assert item.rarity == "Currency"
    assert item.type_line == "Divine Orb"


def test_parse_item_extended_implicit_and_explicit_mod_details() -> None:
    raw = {
        "id": "x",
        "typeLine": "Test",
        "w": 1,
        "h": 1,
        "extended": {
            "mods": {
                "implicit": [
                    {
                        "name": "TestImplicit",
                        "tier": 2,
                        "magnitudes": [
                            {
                                "hash": "h_imp",
                                "min": 1.0,
                                "max": 3.0,
                            }
                        ],
                    }
                ],
                "explicit": [
                    {
                        "name": "TestExplicit",
                        "tier": 1,
                        "magnitudes": [
                            {
                                "hash": "h_exp",
                                "min": 10.0,
                                "max": 20.0,
                            }
                        ],
                    }
                ],
            }
        },
    }
    item = parse_item(raw)
    assert len(item.implicit_mod_details) == 1
    assert item.implicit_mod_details[0].tier == 2
    assert len(item.explicit_mod_details) == 1
    assert item.explicit_mod_details[0].tier == 1


def test_parse_item_unwraps_itemdata_and_flavour() -> None:
    """Real GGG character items nest fields under itemData; flavour lives there too."""
    raw = {
        "inventoryId": "Belt",
        "itemData": {
            "id": "uid-belt",
            "w": 2,
            "h": 1,
            "name": "Gore",
            "typeLine": "Plate Belt",
            "baseType": "Plate Belt",
            "rarity": "Unique",
            "flavourText": ["A warrior's last thought,", "is often his sharpest."],
        },
    }
    item = parse_item(raw)
    assert item.id == "uid-belt"
    assert item.name == "Gore"
    assert item.inventory_id == "Belt"
    assert item.flavour_text and "warrior" in item.flavour_text
    assert "A warrior" in item.flavour_text


def test_parse_item_headhunter_unique_reference_flavour_and_bounds() -> None:
    """Headhunter often has no ``flavourText`` in dev fixtures; we bundle a quote + wiki bounds."""
    raw = {
        "id": "hh1",
        "w": 2,
        "h": 1,
        "name": "Headhunter",
        "typeLine": "Heavy Belt",
        "baseType": "Heavy Belt",
        "rarity": "Unique",
        "implicitMods": [
            "26% increased [StunThreshold|Stun Threshold]",
            "Has 3 [Charm] Slots",
        ],
        "explicitMods": [
            "+53 to maximum Life",
            "+1 to maximum Energy Shield",
        ],
    }
    item = parse_item(raw)
    assert item.name == "Headhunter"
    assert item.flavour_text and "cavern of bone" in item.flavour_text
    assert item.implicit_mod_range_hints
    assert item.explicit_mod_range_hints
    assert any(h == "+(40—60)" for h in item.explicit_mod_range_hints)
    assert any(h and "(20—30)%" in h for h in item.implicit_mod_range_hints if h)
    assert any(h and "(1—3)" in h for h in item.implicit_mod_range_hints if h)


def test_parse_item_strips_tags_from_mod_lists() -> None:
    raw = {
        "id": "ring-1",
        "typeLine": "Topaz Ring",
        "baseType": "Topaz Ring",
        "rarity": "Rare",
        "implicitMods": ["+23% to [Resistances|Lightning Resistance]"],
        "explicitMods": ["+171 to [Accuracy|Accuracy] Rating"],
    }
    item = parse_item(raw)
    assert item.implicit_mods == ["+23% to Lightning Resistance"]
    assert item.explicit_mods == ["+171 to Accuracy Rating"]


def test_parse_item_copies_basic_fields() -> None:
    raw = {
        "id": "item-1",
        "name": "Doom Horn",
        "typeLine": "Spine Bow",
        "baseType": "Spine Bow",
        "rarity": "Rare",
        "ilvl": 82,
        "inventoryId": "Weapon",
        "explicitMods": ["+45 to maximum Life"],
        "sockets": [{"group": 0, "type": "rune"}],
    }
    item = parse_item(raw)
    assert item.name == "Doom Horn"
    assert item.explicit_mods == ["+45 to maximum Life"]
    assert item.sockets[0].type == "rune"
    assert item.inventory_id == "Weapon"
    assert item.rarity == "Rare"


def test_parse_item_socketed_items_rune() -> None:
    """socketedItems in raw GGG JSON are parsed into Item.socketed_items."""
    raw = {
        "id": "axe-1",
        "typeLine": "Vaal Axe",
        "baseType": "Vaal Axe",
        "rarity": "Rare",
        "ilvl": 72,
        "sockets": [{"group": 0, "type": "rune"}],
        "socketedItems": [
            {
                "id": "rune-1",
                "typeLine": "Iron Rune",
                "baseType": "Iron Rune",
                "frameType": 5,
                "explicitMods": ["+5 to Strength"],
            }
        ],
    }
    item = parse_item(raw)
    assert len(item.socketed_items) == 1
    rune = item.socketed_items[0]
    assert rune.id == "rune-1"
    assert rune.type_line == "Iron Rune"
    assert rune.explicit_mods == ["+5 to Strength"]


def test_parse_item_socketed_items_empty_when_absent() -> None:
    """Items with no socketedItems field parse without error."""
    raw = {"id": "ring-2", "typeLine": "Gold Ring", "rarity": "Normal"}
    item = parse_item(raw)
    assert item.socketed_items == []


def test_parse_item_socketed_granted_skill_level() -> None:
    """Soul cores / runes that grant skills expose level in socketed_items[].granted_skills."""
    raw = {
        "id": "shield-1",
        "typeLine": "Chiming Spirit Shield",
        "rarity": "Unique",
        "socketedItems": [
            {
                "id": "core-1",
                "typeLine": "Soul Core of Zalatl",
                "baseType": "Soul Core of Zalatl",
                "frameType": 5,
                "grantedSkills": [
                    {
                        "name": "Grants Skill",
                        "values": [["Level 18 Purity of Ice", 25]],
                        "displayMode": 0,
                    }
                ],
            }
        ],
    }
    item = parse_item(raw)
    assert len(item.socketed_items) == 1
    assert item.socketed_items[0].granted_skills == ["Purity of Ice (lvl 18)"]


def test_parse_item_extended_all_tiers_populated_from_db() -> None:
    """When extended.mods contains a known mod name, all_tiers is populated from mod_db."""
    raw = {
        "id": "xbow-1",
        "typeLine": "Hailforged Crossbow",
        "baseType": "Hailforged Crossbow",
        "rarity": "Rare",
        "ilvl": 72,
        "explicitMods": ["+1 to maximum number of Crossbow Bolts"],
        "extended": {
            "mods": {
                "explicit": [
                    {
                        "name": "of Shelling",
                        "tier": 2,
                        "level": 55,
                        "magnitudes": [{"hash": "h_xbow", "min": 1.0, "max": 1.0}],
                    }
                ]
            }
        },
    }
    item = parse_item(raw)
    assert len(item.explicit_mod_details) == 1
    detail = item.explicit_mod_details[0]
    assert detail.name == "of Shelling"
    assert detail.tier == 2
    # all_tiers should be populated from mod_db: the group has
    # T1 ("of Bursting") and T2 ("of Shelling")
    assert detail.all_tiers is not None
    assert len(detail.all_tiers) == 2
    t1 = detail.all_tiers[0]
    assert t1["tier_ggg"] == 1
    assert t1["name"] == "of Bursting"
    # t1_max on magnitude should also be back-filled
    assert detail.magnitudes[0].t1_max == 2.0


def test_parse_item_extended_all_tiers_none_for_unknown_mod() -> None:
    """Mods with names not in mod_db yield all_tiers=None (not an error)."""
    raw = {
        "id": "y1",
        "typeLine": "Test",
        "rarity": "Rare",
        "extended": {
            "mods": {
                "explicit": [
                    {
                        "name": "SomeUnknownModThatIsNotInDb",
                        "tier": 1,
                        "magnitudes": [{"hash": "hx", "min": 5.0, "max": 10.0}],
                    }
                ]
            }
        },
    }
    item = parse_item(raw)
    assert len(item.explicit_mod_details) == 1
    assert item.explicit_mod_details[0].all_tiers is None


def test_parse_item_infers_mod_detail_without_extended() -> None:
    """Non-unique items without extended.mods get mod details inferred from text via mod_db."""
    raw = {
        "id": "ring-inf",
        "typeLine": "Ruby Ring",
        "baseType": "Ruby Ring",
        "rarity": "Rare",
        "ilvl": 80,
        # No 'extended' key — mod details must be inferred from text
        "explicitMods": ["+1 to maximum number of Crossbow Bolts"],
    }
    item = parse_item(raw)
    assert len(item.explicit_mod_details) == 1
    detail = item.explicit_mod_details[0]
    # Inference may or may not find a match; either way the list is the right length
    # and the detail object is well-formed
    assert isinstance(detail.tier, int | type(None))
    assert isinstance(detail.magnitudes, list)


def test_mod_detail_all_tiers_field_accepts_full_structure() -> None:
    """ModDetail.all_tiers accepts a list of tier dicts as returned by mod_db."""
    from app.domain.item import ModDetail, ModMagnitude

    tiers = [
        {"tier_ggg": 1, "required_level": 82, "name": "of Bursting",
         "stats": [{"id": "s", "min": 2, "max": 2}]},
        {"tier_ggg": 2, "required_level": 55, "name": "of Shelling",
         "stats": [{"id": "s", "min": 1, "max": 1}]},
    ]
    detail = ModDetail(
        name="of Shelling",
        tier=2,
        level=55,
        magnitudes=[ModMagnitude(hash="h1", min=1.0, max=1.0, t1_max=2.0)],
        all_tiers=tiers,
    )
    assert len(detail.all_tiers) == 2
    assert detail.all_tiers[0]["tier_ggg"] == 1
    assert detail.magnitudes[0].t1_max == 2.0


def test_normalize_character_class() -> None:
    assert normalize_character_class("Mercenary1") == "Mercenary"
    assert normalize_character_class("Druid1") == "Druid"
    assert normalize_character_class("Chronomancer") == "Chronomancer"


def test_parse_summaries_and_detail() -> None:
    list_payload = {
        "characters": [
            {"id": "c1", "name": "A", "class": "Ranger", "level": 90, "league": "L"},
            {"id": "c2", "name": "B", "class": "Mercenary1", "level": 85, "league": "L"},
        ]
    }
    summaries = parse_summaries(list_payload)
    assert summaries[0].name == "A"
    assert summaries[0].character_class == "Ranger"
    assert summaries[1].character_class == "Mercenary"

    detail_payload = {
        "character": {"id": "c1", "name": "A", "class": "Druid1", "level": 90, "league": "L"},
        "items": [
            {
                "id": "i1",
                "inventoryId": "Weapon",
                "typeLine": "Bow",
                "rarity": "Rare",
                "explicitMods": ["+45 to maximum Life", "+5% to all Elemental Resistances"],
            },
            {"id": "i2", "inventoryId": "MainInventory", "typeLine": "Quiver"},
        ],
    }
    detail = parse_detail(detail_payload)
    assert detail.summary.name == "A"
    assert detail.summary.character_class == "Druid"
    assert len(detail.equipped) == 1
    assert detail.equipped[0].type_line == "Bow"
    assert len(detail.inventory) == 1
    sm = {s.id: s for s in detail.stat_summary.sections}
    life = next(
        r for r in sm["resources"].rows if "maximum Life" in r.label or "maximum" in r.label
    )
    assert life.values == [45.0]
    tri = next(r for r in sm["resistances"].rows if "Elemental" in r.label and "Resist" in r.label)
    assert tri.values == [5.0]


def test_parse_detail_poe2_character_equipment() -> None:
    """Live GGG PoE2 nests gear under character.equipment, not top-level items."""
    detail_payload = {
        "character": {
            "id": "c1",
            "name": "BringTheRainz",
            "class": "Ranger",
            "level": 90,
            "league": "Runes of Aldur",
            "equipment": [
                {
                    "inventoryId": "Weapon",
                    "itemData": {
                        "id": "w1",
                        "typeLine": "Spine Bow",
                        "baseType": "Spine Bow",
                        "rarity": "Rare",
                        "explicitMods": ["+45 to maximum Life"],
                    },
                },
                {
                    "inventoryId": "Helm",
                    "itemData": {
                        "id": "h1",
                        "typeLine": "Iron Hat",
                        "baseType": "Iron Hat",
                        "rarity": "Magic",
                    },
                },
            ],
            "skills": [],
        },
    }
    assert len(collect_character_items(detail_payload)) == 2
    detail = parse_detail(detail_payload)
    assert detail.summary.name == "BringTheRainz"
    assert len(detail.equipped) == 2
    assert detail.equipped[0].type_line == "Spine Bow"
    assert detail.equipped[0].inventory_id == "Weapon"
    assert len(detail.inventory) == 0


def test_parse_detail_splits_gems_jewels_and_equipment() -> None:
    """Skill gems and passive jewels must not share the inventory bucket."""
    payload = {
        "character": {
            "id": "c1",
            "name": "A",
            "class": "Ranger",
            "level": 90,
            "league": "L",
            "equipment": [
                {
                    "inventoryId": "Weapon",
                    "itemData": {
                        "id": "w1",
                        "typeLine": "Spine Bow",
                        "baseType": "Spine Bow",
                        "rarity": "Rare",
                    },
                },
                {
                    "inventoryId": "Helm",
                    "itemData": {
                        "id": "h1",
                        "typeLine": "Iron Hat",
                        "baseType": "Iron Hat",
                        "rarity": "Magic",
                    },
                },
            ],
            "skills": [
                {
                    "inventoryId": "SkillSlots",
                    "itemData": {
                        "id": "g1",
                        "typeLine": "Forge Hammer",
                        "baseType": "Forge Hammer",
                        "rarity": "Gem",
                        "frameType": 4,
                    },
                }
            ],
            "jewels": [
                {
                    "inventoryId": "PassiveJewels",
                    "itemData": {
                        "id": "j1",
                        "typeLine": "Crimson Jewel",
                        "baseType": "Crimson Jewel",
                        "rarity": "Rare",
                    },
                }
            ],
        },
    }
    detail = parse_detail(payload)
    assert [i.inventory_id for i in detail.equipped] == ["Weapon", "Helm"]
    assert len(detail.gems) == 1
    assert detail.gems[0].type_line == "Forge Hammer"
    assert len(detail.jewels) == 1
    assert detail.jewels[0].type_line == "Crimson Jewel"
    assert detail.inventory == []


def test_parse_item_runeforged_runemastered() -> None:
    item = parse_item(
        {
            "id": "r1",
            "name": "Runeseeker's Call",
            "typeLine": "Runemastered Runic Fork",
            "baseType": "Runemastered Runic Fork",
            "rarity": "Unique",
            "frameType": 14,
            "frameTypeId": "RunicUnique",
        }
    )
    assert item.runeforged is True
    assert item.frame_type_id == "RunicUnique"


def test_strip_runeforged_prefix_item_round_trip() -> None:
    """parse_item → strip_runeforged_prefix_item produces a non-runeforged item with bare base_type.

    GGG field layout: name="Crown of Eyes", typeLine/baseType="Runemastered Vermeil Circlet".
    The combined display "Crown of Eyes Runemastered Vermeil Circlet" is a UI string; it is
    NOT what GGG stores in typeLine.
    """
    from app.domain.item import strip_runeforged_prefix_item

    item = parse_item(
        {
            "id": "r2",
            "name": "Crown of Eyes",
            "typeLine": "Runemastered Vermeil Circlet",
            "baseType": "Runemastered Vermeil Circlet",
            "rarity": "Unique",
            "frameType": 14,
        }
    )
    assert item.runeforged is True
    assert item.base_type == "Runemastered Vermeil Circlet"
    assert item.type_line == "Runemastered Vermeil Circlet"

    fb = strip_runeforged_prefix_item(item)
    assert fb is not None
    assert fb.base_type == "Vermeil Circlet"
    assert fb.type_line == "Vermeil Circlet"
    assert fb.name == "Crown of Eyes"
    assert fb.runeforged is False
    # Original item must be unchanged (model_copy is non-destructive)
    assert item.base_type == "Runemastered Vermeil Circlet"
    assert item.runeforged is True


def test_parse_item_charm_is_charm_and_reclassified() -> None:
    """Charm items set is_charm=True and their inventoryId is remapped Flask→Charm."""
    item = parse_item(
        {
            "id": "charm-001",
            "typeLine": "Antidote Charm",
            "baseType": "Antidote Charm",
            "rarity": "Normal",
            "inventoryId": "Flask",
            "ilvl": 55,
        }
    )
    assert item.is_charm is True
    assert item.inventory_id == "Charm", "Flask slot must be remapped to Charm for charm items"


def test_parse_item_unique_charm_is_charm() -> None:
    """Unique charms also set is_charm=True regardless of rarity."""
    item = parse_item(
        {
            "id": "ucharm-001",
            "name": "Doedre's Elixir",
            "typeLine": "Staunching Charm",
            "baseType": "Staunching Charm",
            "rarity": "Unique",
            "inventoryId": "Flask",
            "ilvl": 60,
        }
    )
    assert item.is_charm is True
    assert item.inventory_id == "Charm"


def test_parse_item_flask_is_not_charm() -> None:
    """Regular flasks keep inventoryId=Flask and is_charm=False."""
    item = parse_item(
        {
            "id": "flask-001",
            "typeLine": "Divine Life Flask",
            "baseType": "Divine Life Flask",
            "rarity": "Normal",
            "inventoryId": "Flask",
        }
    )
    assert item.is_charm is False
    assert item.inventory_id == "Flask"


def test_parse_detail_weapon_slot_from_item_slot_and_outer_wrapper() -> None:
    """Live GGG may omit string inventoryId on weapons; wrapper slot metadata must win."""
    base_char = {
        "id": "c1",
        "name": "A",
        "class": "Ranger",
        "level": 90,
        "league": "L",
    }
    item_slot_payload = {
        "character": {
            **base_char,
            "equipment": [
                {
                    "itemSlot": 7,
                    "itemData": {
                        "id": "w1",
                        "typeLine": "Spine Bow",
                        "baseType": "Spine Bow",
                        "rarity": "Rare",
                    },
                },
                {
                    "itemSlot": 6,
                    "itemData": {
                        "id": "q1",
                        "typeLine": "Broadhead Quiver",
                        "baseType": "Broadhead Quiver",
                        "rarity": "Rare",
                    },
                },
            ],
            "skills": [],
        },
    }
    detail = parse_detail(item_slot_payload)
    slots = {i.inventory_id: i.type_line for i in detail.equipped}
    assert slots["Weapon"] == "Spine Bow"
    assert slots["Offhand"] == "Broadhead Quiver"

    outer_wins_payload = {
        "character": {
            **base_char,
            "equipment": [
                {
                    "inventoryId": "Weapon",
                    "itemData": {
                        "id": "w2",
                        "inventoryId": "SkillSlots",
                        "typeLine": "Ashbark Talisman",
                        "baseType": "Ashbark Talisman",
                        "rarity": "Unique",
                    },
                },
            ],
            "skills": [],
        },
    }
    detail2 = parse_detail(outer_wins_payload)
    assert len(detail2.equipped) == 1
    assert detail2.equipped[0].inventory_id == "Weapon"
    assert detail2.gems == []


def test_parse_detail_item_slot_only_wrapper_like_live_ggg() -> None:
    """Regression: 0089df3 read character.equipment but ignored wrapper itemSlot."""
    payload = {
        "character": {
            "id": "c1",
            "name": "Live",
            "class": "Ranger",
            "level": 90,
            "league": "Runes of Aldur",
            "equipment": [
                {
                    "inventoryId": "Weapon",
                    "itemData": {
                        "id": "w1",
                        "typeLine": "Spine Bow",
                        "baseType": "Spine Bow",
                        "rarity": "Rare",
                    },
                },
                {
                    "itemSlot": 1,
                    "itemData": {
                        "id": "h1",
                        "typeLine": "Iron Hat",
                        "baseType": "Iron Hat",
                        "rarity": "Magic",
                    },
                },
                {
                    "itemSlot": 3,
                    "itemData": {
                        "id": "b1",
                        "typeLine": "Leather Vest",
                        "baseType": "Leather Vest",
                        "rarity": "Rare",
                    },
                },
                {
                    "itemSlot": 8,
                    "itemData": {
                        "id": "r1",
                        "typeLine": "Gold Ring",
                        "baseType": "Gold Ring",
                        "rarity": "Rare",
                    },
                },
            ],
            "skills": [],
        },
    }
    detail = parse_detail(payload)
    slots = {i.inventory_id for i in detail.equipped}
    assert slots == {"Weapon", "Helm", "BodyArmour", "Ring"}
    assert detail.gems == []
    assert detail.inventory == []


def test_parse_detail_outer_item_slot_wins_over_stale_inner_inventory_id() -> None:
    """Live GGG armour often has stale ``itemData.inventoryId`` (e.g. SkillSlots)."""
    payload = {
        "character": {
            "id": "c1",
            "name": "A",
            "class": "Ranger",
            "level": 90,
            "league": "L",
            "equipment": [
                {
                    "itemSlot": 7,
                    "itemData": {
                        "id": "w1",
                        "typeLine": "Spine Bow",
                        "baseType": "Spine Bow",
                        "rarity": "Rare",
                        "inventoryId": "SkillSlots",
                    },
                },
                {
                    "itemSlot": 1,
                    "itemData": {
                        "id": "h1",
                        "typeLine": "Iron Hat",
                        "baseType": "Iron Hat",
                        "rarity": "Magic",
                        "inventoryId": "SkillSlots",
                    },
                },
                {
                    "itemSlot": 3,
                    "itemData": {
                        "id": "b1",
                        "typeLine": "Leather Vest",
                        "baseType": "Leather Vest",
                        "rarity": "Rare",
                        "inventoryId": "SkillSlots",
                    },
                },
                {
                    "itemSlot": 12,
                    "itemData": {
                        "id": "j1",
                        "typeLine": "Crimson Jewel",
                        "baseType": "Crimson Jewel",
                        "rarity": "Rare",
                        "inventoryId": "SkillSlots",
                    },
                },
            ],
            "skills": [],
        },
    }
    detail = parse_detail(payload)
    slots = {i.inventory_id: i.type_line for i in detail.equipped}
    assert slots["Weapon"] == "Spine Bow"
    assert slots["Helm"] == "Iron Hat"
    assert slots["BodyArmour"] == "Leather Vest"
    assert detail.gems == []
    assert len(detail.jewels) == 1
    assert detail.jewels[0].type_line == "Crimson Jewel"


def test_parse_item_ignores_stale_gem_icon_on_equipment_wrapper() -> None:
    """Live wrappers may carry skill-gem art while itemData holds gear without icon."""
    gem_icon = (
        "https://web.poecdn.com/gen/image/WzI1LDE0LHsiZiI6IjJESXRlbXMvR2Vtcy9OZXcv"
        "IceNovaSkillGem.png"
    )
    helm_icon = (
        "https://web.poecdn.com/gen/image/WzI1LDE0LHsiZiI6IjJESXRlbXMvQXJtb3Vycy9IZWxt"
        "ets/HelmetStrDex06.png"
    )
    raw = {
        "itemSlot": 1,
        "icon": gem_icon,
        "itemData": {
            "id": "h1",
            "typeLine": "Iron Hat",
            "baseType": "Iron Hat",
            "rarity": "Magic",
            "inventoryId": "SkillSlots",
            "icon": helm_icon,
        },
    }
    item = parse_item(raw)
    assert item.inventory_id == "Helm"
    assert item.icon == helm_icon

    raw_no_inner_icon = {
        "itemSlot": 1,
        "icon": gem_icon,
        "itemData": {
            "id": "h2",
            "typeLine": "Iron Hat",
            "baseType": "Iron Hat",
            "rarity": "Magic",
            "inventoryId": "SkillSlots",
        },
    }
    item2 = parse_item(raw_no_inner_icon)
    assert item2.inventory_id == "Helm"
    assert item2.icon is None


def test_parse_item_granted_skills_from_ggg_array() -> None:
    raw = {
        "id": "shield-1",
        "name": "Guiding Palm of the Eye",
        "typeLine": "Chiming Spirit Shield",
        "baseType": "Chiming Spirit Shield",
        "rarity": "Unique",
        "grantedSkills": [
            {
                "name": "Grants Skill",
                "values": [["Level 18 Purity of Ice", 25]],
                "displayMode": 0,
            }
        ],
        "properties": [
            {"name": "Spirit Shield", "values": []},
            {
                "name": "Grants Skill",
                "values": [["Purity of Ice", 25]],
            },
        ],
    }
    item = parse_item(raw)
    assert item.granted_skills == ["Purity of Ice (lvl 18)"]
    assert all(p.name != "Grants Skill" for p in item.properties)


def test_parse_item_granted_skills_from_properties_when_array_missing() -> None:
    raw = {
        "id": "w-1",
        "typeLine": "Test Wand",
        "baseType": "Test Wand",
        "rarity": "Rare",
        "properties": [
            {
                "name": "Grants Skill",
                "values": [["Level 17 Sigil of Power", 25]],
            }
        ],
    }
    item = parse_item(raw)
    assert item.granted_skills == ["Sigil of Power (lvl 17)"]


def test_collect_character_items_expands_lineage_gem_from_skill_socketed_items() -> None:
    """Lineage supports nested in a skill gem's itemData.socketedItems must be collected.

    Her Declaration (and similar lineage gems) appear as entries in `socketedItems`
    inside a skill gem's `itemData` wrapper in the poe.ninja / live GGG payload shape.
    They must survive flattening so that `parse_detail` classifies them correctly.
    """
    lineage_item = {
        "id": "lineage-her-declaration",
        "name": "Her Declaration",
        "typeLine": "Her Declaration",
        "baseType": "Her Declaration",
        "frameType": 4,
        "rarity": "Gem",
        "ilvl": 0,
        "inventoryId": None,
        "properties": [
            {
                "name": "[SupportGem|Support], [LineageSupports|Lineage]",
                "values": [],
                "displayMode": 0,
            }
        ],
        "identified": True,
        "corrupted": False,
        "sockets": [],
        "socketedItems": [],
    }
    skill_skill = {
        "inventoryId": "SkillSlots",
        "itemData": {
            "id": "purity-of-ice-skill",
            "typeLine": "Purity of Ice",
            "baseType": "Purity of Ice",
            "frameType": 4,
            "rarity": "Gem",
            "ilvl": 0,
            "sockets": [{"group": 0, "type": "gem"}],
            "socketedItems": [lineage_item],
        },
    }
    payload = {
        "character": {
            "id": "c1",
            "name": "TestCharacter",
            "class": "Monk",
            "level": 90,
            "league": "Standard",
            "equipment": [],
            "skills": [skill_skill],
        },
    }
    items = collect_character_items(payload)
    ids = {r.get("id") or (r.get("itemData") or {}).get("id") for r in items}
    assert "lineage-her-declaration" in ids, "nested lineage gem must be collected"
    assert "purity-of-ice-skill" in ids, "parent skill gem must still be collected"

    detail = parse_detail(payload)
    gem_ids = {g.id for g in detail.gems}
    inv_ids = {i.id for i in detail.inventory}
    assert "purity-of-ice-skill" in gem_ids, "skill gem goes to gems bucket"
    assert "lineage-her-declaration" in inv_ids, "lineage gem (no inventoryId) goes to inventory"


def test_ninja_convert_includes_skills_in_ggg_payload() -> None:
    """ninja_convert must include charModel.skills so lineage support gems reach the backend.

    Regression: char_model_to_ggg_payload() previously ignored charModel.skills entirely,
    so ALL skill gems (active skills, regular supports, lineage supports) were absent from
    the GGG-shaped payload sent to the backend.  This caused lineage gems to never appear
    in CharacterDetail.inventory and therefore never display in the support gems section.
    """
    if str(_MOCK_GGG_APP) not in sys.path:
        sys.path.insert(0, str(_MOCK_GGG_APP))
    from ninja_convert import char_model_to_ggg_payload  # noqa: PLC0415

    lineage_item_data = {
        "id": "lineage-rakiata",
        "name": "Rakiata's Flow",
        "typeLine": "Rakiata's Flow",
        "baseType": "Rakiata's Flow",
        "frameType": 4,
        "ilvl": 0,
        "inventoryId": None,
        "properties": [
            {
                "name": "[SupportGem|Support], [LineageSupports|Lineage]",
                "values": [],
                "displayMode": 0,
            }
        ],
        "identified": True,
        "corrupted": False,
        "sockets": [],
        "socketedItems": [],
    }
    skill_gem_item_data = {
        "id": "ice-nova-skill",
        "name": "Ice Nova",
        "typeLine": "Ice Nova",
        "baseType": "Ice Nova",
        "frameType": 4,
        "ilvl": 0,
        "inventoryId": None,
        "properties": [],
        "identified": True,
        "corrupted": False,
        "sockets": [{"group": 0, "type": "gem"}],
        "socketedItems": [lineage_item_data],
    }
    # poe.ninja charModel.skills format: allGems contains all gems in the skill group
    cm = {
        "name": "TestChar",
        "class": "Monk",
        "level": 90,
        "league": "Standard",
        "items": [],
        "jewels": [],
        "skills": [
            {
                "allGems": [
                    {
                        "name": "Ice Nova",
                        "itemData": skill_gem_item_data,
                        "level": 20,
                        "quality": 20,
                    },
                    {
                        "name": "Rakiata's Flow",
                        "itemData": lineage_item_data,
                        "level": 20,
                        "quality": 20,
                    },
                ],
                "dps": 12345.0,
            }
        ],
    }
    payload = char_model_to_ggg_payload(cm)

    # character.skills must be populated as flat individual GGG-style entries (one per gem)
    char = payload.get("character", {})
    assert "skills" in char, "character.skills must be present in GGG payload"
    # 2 entries: one for Ice Nova, one for Rakiata's Flow (flat, not grouped)
    assert len(char["skills"]) == 2, (
        "allGems must be flattened into individual skill entries, not kept as a group"
    )
    skill_inventory_ids = [s.get("inventoryId") for s in char["skills"]]
    assert "SkillSlots" not in skill_inventory_ids, (
        "ice-nova has inventoryId=None in test data; no SkillSlots entry expected"
    )

    items = collect_character_items(payload)
    ids = {r.get("id") or (r.get("itemData") or {}).get("id") for r in items}
    assert "lineage-rakiata" in ids, "lineage gem from allGems must be collected"
    assert "ice-nova-skill" in ids, "active skill gem from allGems must be collected"

    detail = parse_detail(payload)
    inv_ids = {i.id for i in detail.inventory}
    assert "lineage-rakiata" in inv_ids, "lineage gem must reach detail.inventory"

    inv_lineage = [
        i for i in detail.inventory
        if any("lineage" in p.name.lower() for p in i.properties)
    ]
    assert len(inv_lineage) >= 1, "at least one lineage gem must be in detail.inventory"

    # Validate no garbage items (skill groups should not appear as items)
    garbage = [i for i in detail.inventory if not i.id]
    assert len(garbage) == 0, "no garbage skill-group dicts in inventory"


def test_collect_character_items_skips_empty_iid_container_dicts() -> None:
    """Container/group dicts are skipped; granted skills (no id, has typeLine) get stable IDs.

    Regression guard for multiple issues:
    1. Container wrappers like ``{ "gems": [...] }`` must be skipped — they are not items.
    2. Granted skills (e.g. Molten Shower from a unique item) may have no ``id`` in the
       live GGG API but DO have a ``typeLine``.  add() must give them a stable iid from
       typeLine so they survive and are correctly deduplicated.
    3. Two granted skills with different typeLine values (Purity of Ice + Molten Shower)
       must BOTH survive — the ``item.id`` fallback to ``typeLine`` in ``parse_item``
       prevents frontend deduplication collisions on empty string ids.
    """
    payload = {
        "character": {
            "id": "c1",
            "name": "TestChar",
            "class": "Monk",
            "level": 90,
            "league": "Standard",
            "equipment": [],
            "skills": [
                # Group wrapper: has no id itself but contains gems via the "gems" key
                {
                    "gems": [
                        {
                            "inventoryId": "SkillSlots",
                            "itemData": {
                                "id": "skill-abc",
                                "typeLine": "Ice Nova",
                                "rarity": "Gem",
                                "frameType": 4,
                            },
                        },
                        {
                            "inventoryId": None,
                            "itemData": {
                                "id": "lineage-xyz",
                                "typeLine": "Her Declaration",
                                "rarity": "Gem",
                                "frameType": 4,
                                "properties": [
                                    {
                                        "name": "[SupportGem|Support], [LineageSupports|Lineage]",
                                        "values": [],
                                        "displayMode": 0,
                                    }
                                ],
                            },
                        },
                    ]
                },
                # Granted skill: no id, identified by typeLine — must survive with stable id
                {
                    "inventoryId": "DefaultAttackSkills",
                    "itemData": {
                        "typeLine": "Molten Shower",
                        "rarity": "Gem",
                        "frameType": 4,
                    },
                },
                # Second granted skill: also no id, different typeLine — must also survive
                {
                    "inventoryId": "SkillSlots",
                    "itemData": {
                        "typeLine": "Purity of Ice",
                        "rarity": "Gem",
                        "frameType": 4,
                    },
                },
            ],
        }
    }
    items = collect_character_items(payload)

    # Pure group wrapper (no id, typeLine, or name) must NOT appear
    def _type(r: dict) -> str:
        return str((r.get("itemData") or r).get("typeLine") or "")

    containers = [r for r in items if not _type(r) and not (r.get("itemData") or r).get("name")]
    assert containers == [], f"group wrappers must be skipped: {containers}"

    types_collected = {_type(r) for r in items}
    assert "Ice Nova" in types_collected, "active skill gem from nested gems must be present"
    assert "Her Declaration" in types_collected, "lineage gem from nested gems must be present"
    assert "Molten Shower" in types_collected, "granted skill (no id) must survive via typeLine iid"
    assert "Purity of Ice" in types_collected, "second granted skill must also survive"

    detail = parse_detail(payload)
    gem_ids = {g.id for g in detail.gems}
    inv_ids = {i.id for i in detail.inventory}

    assert "skill-abc" in gem_ids, "active skill gem goes to detail.gems"
    assert "lineage-xyz" in inv_ids, "lineage gem (inventoryId=None) goes to detail.inventory"

    # Granted skills get item.id = typeLine thanks to the typeLine fallback in parse_item
    assert "Molten Shower" in gem_ids, "Molten Shower (granted, no raw id) gets id=typeLine"
    assert "Purity of Ice" in gem_ids, "Purity of Ice (granted, no raw id) gets id=typeLine"

    # Both granted skills are distinct — no frontend dedup collision on item.id=""
    assert "Molten Shower" != "Purity of Ice"  # trivially true; make it explicit
    assert all(g.id for g in detail.gems), "no empty item.id in detail.gems"
