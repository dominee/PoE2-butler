"""Convert poe.ninja character exports to GGG API fixture format.

poe.ninja shape:
  { "charModel": { "account", "name", "league", "level", "class",
                   "items":  [{ "itemData": {...}, "itemSlot": N }],
                   "jewels": [{ "itemData": {...}, "itemSlot": N }] } }

GGG API character shape (what mock-ggg serves):
  { "character": { "id", "name", "realm", "class", "level", "league", "experience" },
    "items": [ <flat item dicts> ] }
"""

import json
import hashlib
from pathlib import Path

SAMPLES = Path(__file__).parent
FIXTURES = SAMPLES.parent / "app" / "fixtures"

SAMPLES_MAP = {
    "Catticiaan":      SAMPLES / "tactician.json",
    "NextWizardKing":  SAMPLES / "chrono.json",
    "IamGothmog":      SAMPLES / "druid.json",
}

FRAME_TO_RARITY = {
    0: "Normal", 1: "Magic", 2: "Rare",
    3: "Unique", 4: "Gem", 5: "Currency",
    6: "Quest",  9: "Relic",
}

# Fields stripped from every item (top-level and socketed).
# socketedItems is NOT in this set — it is handled recursively below.
_STRIP = frozenset({
    "doubleCorrupted", "desecrated", "desecratedMods", "bondedMods",
    "grantedSkills", "runeMods", "support", "gemTabs",
    "gemSkill", "gemBackground", "weaponRequirements", "supportGemRequirements",
    "gemSockets", "iconTierText", "qualityProperty", "artFilename",
    "mutatedMods", "mutated", "scourgeMods", "crucibleMods", "fracturedMods",
    "additionalProperties", "descrText", "secDescrText", "prophecyText", "note",
    "flavourText", "extended", "duplicated", "synthesised", "fractured",
    "replica", "stackSize",
})


def stable_id(name: str) -> str:
    """Deterministic fake UUID from a string."""
    h = hashlib.sha1(name.encode()).hexdigest()
    return f"{h[:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:32]}"


def convert_item_data(raw: dict, *, depth: int = 0) -> dict:
    """Convert a *flat* GGG/poe.ninja item dict (no itemData wrapper).

    ``depth=0``  → top-level item: recursively converts socketedItems.
    ``depth=1``  → socketed item (rune/soul core): socketedItems cleared.
    """
    item = raw.copy()

    item.setdefault("verified", True)
    item.setdefault("identified", True)
    item.setdefault("corrupted", False)

    if not item.get("rarity"):
        item["rarity"] = FRAME_TO_RARITY.get(item.get("frameType", 0), "Normal")

    # Handle socketedItems recursively
    raw_socketed = item.pop("socketedItems", None) or []
    if depth == 0:
        item["socketedItems"] = [
            convert_item_data(si, depth=1)
            for si in raw_socketed
            if isinstance(si, dict)
        ]
    # depth >= 1: runes don't themselves have socketed items; leave field absent

    for key in _STRIP:
        item.pop(key, None)

    # craftedMods / enchantMods are legitimate mod types — keep them
    # (they were erroneously stripped before; remove from _STRIP if present)
    return item


def convert_item(wrapped: dict) -> dict:
    """Convert a poe.ninja {"itemData": {...}, "itemSlot": N} entry."""
    return convert_item_data(wrapped["itemData"])


def convert_character(path: Path, char_name: str) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    cm = data["charModel"]

    character = {
        "id": stable_id(char_name),
        "name": cm["name"],
        "realm": "pc",
        "class": cm["class"],
        "level": cm["level"],
        "league": cm["league"],
        "experience": 0,
    }

    gear   = [convert_item(raw) for raw in cm.get("items",  []) or []]
    jewels = [convert_item(raw) for raw in cm.get("jewels", []) or []]

    return {"character": character, "items": gear + jewels}


def main() -> None:
    users      = json.loads((FIXTURES / "users.json").read_text(encoding="utf-8"))
    characters = json.loads((FIXTURES / "characters.json").read_text(encoding="utf-8"))

    char_list_entries = []
    for char_name, sample_path in SAMPLES_MAP.items():
        print(f"Converting {char_name} from {sample_path.name} …")
        char_data = convert_character(sample_path, char_name)
        characters[char_name] = char_data

        char_list_entries.append({
            "id":         char_data["character"]["id"],
            "name":       char_name,
            "realm":      "pc",
            "class":      char_data["character"]["class"],
            "level":      char_data["character"]["level"],
            "league":     char_data["character"]["league"],
            "experience": 0,
        })
        gear_count   = sum(1 for i in char_data["items"] if i.get("inventoryId") != "PassiveJewels")
        jewel_count  = sum(1 for i in char_data["items"] if i.get("inventoryId") == "PassiveJewels")
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
            {"id": "Standard",                 "realm": "pc", "description": "Standard",                 "current": False},
            {"id": "Fate of the Vaal",         "realm": "pc", "description": "Current challenge league", "current": True},
            {"id": "Hardcore Fate of the Vaal","realm": "pc", "description": "Hardcore temp league",     "current": False},
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
    print("\nDone.")


if __name__ == "__main__":
    main()
