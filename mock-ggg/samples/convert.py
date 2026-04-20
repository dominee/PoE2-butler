"""Convert poe.ninja character exports to GGG API fixture format.

poe.ninja shape:
  { "charModel": { "account", "name", "league", "level", "class",
                   "items": [{ "itemData": {...}, "itemSlot": N }] } }

GGG API character shape (what mock-ggg serves):
  { "character": { "id", "name", "realm", "class", "level", "league", "experience" },
    "items": [ <itemData fields> ] }
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


def stable_id(name: str) -> str:
    """Deterministic fake UUID from character name."""
    h = hashlib.sha1(name.encode()).hexdigest()
    return f"{h[:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:32]}"


def convert_item(raw: dict) -> dict:
    """Strip the poe.ninja wrapper and normalise to GGG API item shape."""
    item = raw["itemData"].copy()

    # Ensure GGG API required fields
    item.setdefault("verified", True)
    item.setdefault("identified", True)
    item.setdefault("corrupted", False)

    # poe.ninja uses frameType; derive rarity string when absent
    if "rarity" not in item or not item["rarity"]:
        frame = item.get("frameType", 0)
        item["rarity"] = {
            0: "Normal", 1: "Magic", 2: "Rare",
            3: "Unique", 4: "Gem", 5: "Currency",
            6: "Quest", 9: "Relic",
        }.get(frame, "Normal")

    # Remove poe.ninja-only noise that the backend doesn't need
    for key in (
        "doubleCorrupted", "desecrated", "desecratedMods", "bondedMods",
        "grantedSkills", "runeMods", "socketedItems", "support", "gemTabs",
        "gemSkill", "gemBackground", "weaponRequirements", "supportGemRequirements",
        "gemSockets", "iconTierText", "qualityProperty", "artFilename",
        "mutatedMods", "mutated", "scourgeMods", "crucibleMods", "fracturedMods",
        "craftedMods", "enchantMods", "additionalProperties",
        "descrText", "secDescrText", "prophecyText", "note",
        "flavourText", "extended", "duplicated", "synthesised", "fractured",
        "replica", "stackSize",
    ):
        item.pop(key, None)

    return item


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

    items = [convert_item(raw) for raw in cm.get("items", [])]

    return {"character": character, "items": items}


def main() -> None:
    # Load existing fixtures so we can preserve exile_one
    users = json.loads((FIXTURES / "users.json").read_text(encoding="utf-8"))
    characters = json.loads((FIXTURES / "characters.json").read_text(encoding="utf-8"))

    char_list_entries = []
    for char_name, sample_path in SAMPLES_MAP.items():
        print(f"Converting {char_name} from {sample_path.name} …")
        char_data = convert_character(sample_path, char_name)
        characters[char_name] = char_data

        char_list_entries.append({
            "id": char_data["character"]["id"],
            "name": char_name,
            "realm": "pc",
            "class": char_data["character"]["class"],
            "level": char_data["character"]["level"],
            "league": char_data["character"]["league"],
            "experience": 0,
        })
        print(f"  → {len(char_data['items'])} items")

    # Add dominee user (keep exile_one intact)
    users["dominee"] = {
        "profile": {
            "name": "dominee#9275",
            "uuid": stable_id("dominee#9275"),
            "realm": "pc",
            "guild": None,
        },
        "leagues": [
            {"id": "Standard",        "realm": "pc", "description": "Standard",                  "current": False},
            {"id": "Fate of the Vaal","realm": "pc", "description": "Current challenge league",  "current": True},
            {"id": "Hardcore Fate of the Vaal","realm":"pc","description":"Hardcore temp league","current":False},
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
