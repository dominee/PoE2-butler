"""Convert poe.ninja character exports to GGG API fixture format.

Run from repo: ``cd mock-ggg && uv run python samples/convert.py``
(or any cwd if PYTHONPATH includes the mock-ggg root).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.ninja_convert import (  # noqa: E402
    CURRENCY_ICONS,
    convert_item,
    convert_character_file,
    pack_items,
    stable_id,
)

SAMPLES = Path(__file__).parent
FIXTURES = SAMPLES.parent / "app" / "fixtures"

SAMPLES_MAP = {
    "Catticiaan": SAMPLES / "tactician.json",
    "NextWizardKing": SAMPLES / "chrono.json",
    "IamGothmog": SAMPLES / "druid.json",
}


def collect_stash_items_from_character(path: Path, id_prefix: str) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    cm = data["charModel"]
    items = []
    for wrapped in cm.get("items", []) or []:
        item = convert_item(wrapped)
        slot = wrapped.get("itemSlot", 0)
        orig_id = item.get("id", stable_id(f"{id_prefix}-{slot}"))
        item["id"] = f"stash-{id_prefix}-{orig_id[-8:]}"
        item.pop("inventoryId", None)
        items.append(item)
    return items


def build_stashes(leagues: dict[str, list[str]]) -> dict:
    all_stashes: dict = {}

    for league, char_prefixes in leagues.items():
        tab_id_dump = f"{league.lower().replace(' ', '-')}-gear"
        tab_id_currency = f"{league.lower().replace(' ', '-')}-currency"
        tab_id_new = f"{league.lower().replace(' ', '-')}-new"

        established_items: list[dict] = []
        new_items: list[dict] = []

        sample_paths = [SAMPLES_MAP.get(p) for p in char_prefixes if SAMPLES_MAP.get(p)]
        for i, sp in enumerate(sample_paths):
            if sp is None:
                continue
            prefix = char_prefixes[i][:4].lower()
            items = collect_stash_items_from_character(sp, prefix)
            if i < len(sample_paths) - 1:
                established_items.extend(items)
            else:
                new_items.extend(items)

        all_gear = established_items + new_items
        packed_all = pack_items(all_gear)
        packed_prev = pack_items(established_items)

        currency_items = [
            {
                "id": f"{tab_id_currency}-divine",
                "verified": True,
                "w": 1,
                "h": 1,
                "x": 0,
                "y": 0,
                "stackSize": 7,
                "maxStackSize": 10,
                "typeLine": "Divine Orb",
                "baseType": "Divine Orb",
                "rarity": "Currency",
                "identified": True,
                "corrupted": False,
                "icon": CURRENCY_ICONS.get("Divine Orb"),
            },
            {
                "id": f"{tab_id_currency}-chaos",
                "verified": True,
                "w": 1,
                "h": 1,
                "x": 1,
                "y": 0,
                "stackSize": 843,
                "maxStackSize": 5000,
                "typeLine": "Chaos Orb",
                "baseType": "Chaos Orb",
                "rarity": "Currency",
                "identified": True,
                "corrupted": False,
                "icon": CURRENCY_ICONS.get("Chaos Orb"),
            },
            {
                "id": f"{tab_id_currency}-exalt",
                "verified": True,
                "w": 1,
                "h": 1,
                "x": 2,
                "y": 0,
                "stackSize": 14,
                "maxStackSize": 20,
                "typeLine": "Exalted Orb",
                "baseType": "Exalted Orb",
                "rarity": "Currency",
                "identified": True,
                "corrupted": False,
                "icon": CURRENCY_ICONS.get("Exalted Orb"),
            },
            {
                "id": f"{tab_id_currency}-alt",
                "verified": True,
                "w": 1,
                "h": 1,
                "x": 3,
                "y": 0,
                "stackSize": 120,
                "maxStackSize": 5000,
                "typeLine": "Orb of Alteration",
                "baseType": "Orb of Alteration",
                "rarity": "Currency",
                "identified": True,
                "corrupted": False,
                "icon": CURRENCY_ICONS.get("Orb of Alteration"),
            },
            {
                "id": f"{tab_id_currency}-alchemy",
                "verified": True,
                "w": 1,
                "h": 1,
                "x": 4,
                "y": 0,
                "stackSize": 55,
                "maxStackSize": 5000,
                "typeLine": "Orb of Alchemy",
                "baseType": "Orb of Alchemy",
                "rarity": "Currency",
                "identified": True,
                "corrupted": False,
                "icon": CURRENCY_ICONS.get("Orb of Alchemy"),
            },
            {
                "id": f"{tab_id_currency}-vaal",
                "verified": True,
                "w": 1,
                "h": 1,
                "x": 5,
                "y": 0,
                "stackSize": 33,
                "maxStackSize": 20,
                "typeLine": "Vaal Orb",
                "baseType": "Vaal Orb",
                "rarity": "Currency",
                "identified": True,
                "corrupted": False,
                "icon": CURRENCY_ICONS.get("Vaal Orb"),
            },
        ]

        all_stashes[league] = {
            "tabs": [
                {
                    "id": tab_id_dump,
                    "name": "Gear Dump",
                    "type": "PremiumStash",
                    "index": 0,
                    "colour": {"r": 120, "g": 60, "b": 200},
                },
                {
                    "id": tab_id_currency,
                    "name": "Currency",
                    "type": "CurrencyStash",
                    "index": 1,
                    "colour": {"r": 200, "g": 160, "b": 60},
                },
                {
                    "id": tab_id_new,
                    "name": "New Loot",
                    "type": "PremiumStash",
                    "index": 2,
                    "colour": {"r": 60, "g": 180, "b": 80},
                },
            ],
            "contents": {
                tab_id_dump: {"items": packed_all},
                tab_id_currency: {"items": currency_items},
                tab_id_new: {"items": pack_items(list(new_items))},
            },
            "prev_contents": {
                tab_id_dump: {"items": packed_prev},
                tab_id_currency: {"items": currency_items},
                tab_id_new: {"items": []},
            },
        }

    return all_stashes


def main() -> None:
    users = json.loads((FIXTURES / "users.json").read_text(encoding="utf-8"))
    characters = json.loads((FIXTURES / "characters.json").read_text(encoding="utf-8"))

    char_list_entries = []
    for char_name, sample_path in SAMPLES_MAP.items():
        print(f"Converting {char_name} from {sample_path.name} …")
        char_data = convert_character_file(sample_path, char_name)
        characters[char_name] = char_data

        char_list_entries.append(
            {
                "id": char_data["character"]["id"],
                "name": char_name,
                "realm": "pc",
                "class": char_data["character"]["class"],
                "level": char_data["character"]["level"],
                "league": char_data["character"]["league"],
                "experience": 0,
            }
        )
        gear_count = sum(1 for i in char_data["items"] if i.get("inventoryId") != "PassiveJewels")
        jewel_count = sum(1 for i in char_data["items"] if i.get("inventoryId") == "PassiveJewels")
        socketed_sum = sum(len(i.get("socketedItems", [])) for i in char_data["items"])
        print(f"  → {gear_count} gear, {jewel_count} jewels, {socketed_sum} socketed items")

    users["dominee"] = {
        "profile": {
            "name": "dominee#9275",
            "uuid": stable_id("dominee#9275"),
            "realm": "pc",
            "guild": None,
        },
        "leagues": [
            {"id": "Standard", "realm": "pc", "description": "Standard", "current": False},
            {
                "id": "Fate of the Vaal",
                "realm": "pc",
                "description": "Current challenge league",
                "current": True,
            },
            {
                "id": "Hardcore Fate of the Vaal",
                "realm": "pc",
                "description": "Hardcore temp league",
                "current": False,
            },
        ],
        "characters": char_list_entries,
    }

    (FIXTURES / "users.json").write_text(
        json.dumps(users, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print("\nWrote fixtures/users.json")

    (FIXTURES / "characters.json").write_text(
        json.dumps(characters, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print("Wrote fixtures/characters.json")

    print("\nGenerating stashes.json from character items …")
    char_names = list(SAMPLES_MAP.keys())
    leagues = {
        "Fate of the Vaal": char_names,
        "Dawn of the Hunt": char_names[:2],
    }
    stashes = build_stashes(leagues)

    for league, data in stashes.items():
        dump_count = len(
            data["contents"].get(list(data["contents"].keys())[0], {}).get("items", [])
        )
        prev_count = len(
            data["prev_contents"].get(list(data["prev_contents"].keys())[0], {}).get("items", [])
        )
        print(f"  {league}: gear tab {dump_count} items (prev: {prev_count})")

    (FIXTURES / "stashes.json").write_text(
        json.dumps(stashes, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print("Wrote fixtures/stashes.json")
    print("\nDone.")


if __name__ == "__main__":
    main()
