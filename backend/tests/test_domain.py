"""Unit tests for domain normalizers."""

from __future__ import annotations

from app.domain.character import parse_detail, parse_summaries
from app.domain.item import parse_item
from app.domain.league import parse_leagues, pick_current_league


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


def test_parse_summaries_and_detail() -> None:
    list_payload = {
        "characters": [
            {"id": "c1", "name": "A", "class": "Ranger", "level": 90, "league": "L"},
        ]
    }
    summaries = parse_summaries(list_payload)
    assert summaries[0].name == "A"
    assert summaries[0].character_class == "Ranger"

    detail_payload = {
        "character": {"id": "c1", "name": "A", "class": "Ranger", "level": 90, "league": "L"},
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
