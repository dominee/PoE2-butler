"""Convert poe.ninja character exports to GGG API fixture format.

poe.ninja shape:
  { "charModel": { "account", "name", "league", "level", "class",
                   "items":  [{ "itemData": {...}, "itemSlot": N }],
                   "jewels": [{ "itemData": {...}, "itemSlot": N }] } }

GGG API character shape (what mock-ggg serves):
  { "character": { "id", "name", "realm", "class", "level", "league", "experience" },
    "items": [ <flat item dicts> ] }

Also generates stashes.json from character items for realistic mock stash data.
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

# Known PoE2 currency icon URLs (GGG CDN)
CURRENCY_ICONS: dict[str, str] = {
    "Divine Orb":       "https://web.poecdn.com/gen/image/WzI1LDE0LHsiZiI6IjJESXRlbXMvQ3VycmVuY3kvQ3VycmVuY3lNb2RWYWx1ZXMiLCJ3IjoxLCJoIjoxLCJzY2FsZSI6MX1d/e1a54ff97d/CurrencyModValues.png",
    "Chaos Orb":        "https://web.poecdn.com/gen/image/WzI1LDE0LHsiZiI6IjJESXRlbXMvQ3VycmVuY3kvQ3VycmVuY3lSZXJvbGxSYXJlIiwidyI6MSwiaCI6MSwic2NhbGUiOjF9XQ/d119a0d734/CurrencyRerollRare.png",
    "Exalted Orb":      "https://web.poecdn.com/gen/image/WzI1LDE0LHsiZiI6IjJESXRlbXMvQ3VycmVuY3kvQ3VycmVuY3lBZGRNb2RUb1JhcmUiLCJ3IjoxLCJoIjoxLCJzY2FsZSI6MX1d/1e4a9c1e1d/CurrencyAddModToRare.png",
    "Orb of Alteration": "https://web.poecdn.com/gen/image/WzI1LDE0LHsiZiI6IjJESXRlbXMvQ3VycmVuY3kvQ3VycmVuY3lSZXJvbGxNYWdpYyIsInciOjEsImgiOjEsInNjYWxlIjoxfV0=/85fff943e6/CurrencyRerollMagic.png",
    "Orb of Alchemy":   "https://web.poecdn.com/gen/image/WzI1LDE0LHsiZiI6IjJESXRlbXMvQ3VycmVuY3kvQ3VycmVuY3lVcGdyYWRlVG9SYXJlIiwidyI6MSwiaCI6MSwic2NhbGUiOjF9XQ/667f4e9745/CurrencyUpgradeToRare.png",
    "Orb of Transmutation": "https://web.poecdn.com/gen/image/WzI1LDE0LHsiZiI6IjJESXRlbXMvQ3VycmVuY3kvQ3VycmVuY3lVcGdyYWRlVG9NYWdpYyIsInciOjEsImgiOjEsInNjYWxlIjoxfV0=/1b6ace67e5/CurrencyUpgradeToMagic.png",
    "Vaal Orb":         "https://web.poecdn.com/gen/image/WzI1LDE0LHsiZiI6IjJESXRlbXMvQ3VycmVuY3kvQ3VycmVuY3lWYWFsIiwidyI6MSwiaCI6MSwic2NhbGUiOjF9XQ/4e04497800/CurrencyVaal.png",
}


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


def pack_items(items: list[dict], grid_w: int = 12, grid_h: int = 12) -> list[dict]:
    """Assign x,y stash-grid positions to items using greedy first-fit.

    Items that don't fit in the declared grid height are placed on extended rows.
    """
    grid: list[list[bool]] = [[False] * grid_w for _ in range(grid_h * 3)]

    def find_slot(w: int, h: int) -> tuple[int, int] | None:
        for y in range(len(grid) - h + 1):
            for x in range(grid_w - w + 1):
                if all(not grid[yy][xx] for yy in range(y, y + h) for xx in range(x, x + w)):
                    return x, y
        return None

    def mark(x: int, y: int, w: int, h: int) -> None:
        for yy in range(y, y + h):
            for xx in range(x, x + w):
                grid[yy][xx] = True

    placed = []
    for item in items:
        w = max(1, item.get("w", 1))
        h = max(1, item.get("h", 1))
        slot = find_slot(w, h)
        if slot is None:
            # Extend grid and try again
            for _ in range(h):
                grid.append([False] * grid_w)
            slot = find_slot(w, h)
        if slot:
            x, y = slot
            item = dict(item)
            item["x"] = x
            item["y"] = y
            mark(x, y, w, h)
            placed.append(item)
    return placed


def collect_stash_items_from_character(path: Path, id_prefix: str) -> list[dict]:
    """Extract gear items from a poe.ninja export, give them stash IDs."""
    data = json.loads(path.read_text(encoding="utf-8"))
    cm = data["charModel"]
    items = []
    for wrapped in cm.get("items", []) or []:
        item = convert_item(wrapped)
        slot = wrapped.get("itemSlot", 0)
        # Re-ID so stash item IDs are distinct from character item IDs
        orig_id = item.get("id", stable_id(f"{id_prefix}-{slot}"))
        item["id"] = f"stash-{id_prefix}-{orig_id[-8:]}"
        # Remove character-specific inventory slot
        item.pop("inventoryId", None)
        items.append(item)
    return items


def build_stashes(leagues: dict[str, list[str]]) -> dict:
    """Build the full stashes fixture.

    ``leagues`` maps league_id → list of character sample prefixes.
    We build:
      - A "Gear Dump" tab (PremiumStash) with all character gear items.
      - A "Currency" tab (CurrencyStash) with known currency items.
      - A "New Loot" tab (PremiumStash):
          contents  → items from the last character (appears "new" after 2nd refresh)
          prev_contents → empty (so activity log shows them as new items)
    """
    all_stashes: dict = {}

    for league, char_prefixes in leagues.items():
        tab_id_dump    = f"{league.lower().replace(' ', '-')}-gear"
        tab_id_currency = f"{league.lower().replace(' ', '-')}-currency"
        tab_id_new     = f"{league.lower().replace(' ', '-')}-new"

        # ── Gear Dump tab ─────────────────────────────────────────────────
        # First N-1 characters → "established" items (present from first snapshot)
        # Last character → "new" items (added in 2nd snapshot for activity log)
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
        packed_all    = pack_items(all_gear)
        packed_prev   = pack_items(established_items)

        # ── Currency tab ──────────────────────────────────────────────────
        currency_items = [
            {
                "id": f"{tab_id_currency}-divine",
                "verified": True, "w": 1, "h": 1, "x": 0, "y": 0,
                "stackSize": 7, "maxStackSize": 10,
                "typeLine": "Divine Orb", "baseType": "Divine Orb",
                "rarity": "Currency", "identified": True, "corrupted": False,
                "icon": CURRENCY_ICONS.get("Divine Orb"),
            },
            {
                "id": f"{tab_id_currency}-chaos",
                "verified": True, "w": 1, "h": 1, "x": 1, "y": 0,
                "stackSize": 843, "maxStackSize": 5000,
                "typeLine": "Chaos Orb", "baseType": "Chaos Orb",
                "rarity": "Currency", "identified": True, "corrupted": False,
                "icon": CURRENCY_ICONS.get("Chaos Orb"),
            },
            {
                "id": f"{tab_id_currency}-exalt",
                "verified": True, "w": 1, "h": 1, "x": 2, "y": 0,
                "stackSize": 14, "maxStackSize": 20,
                "typeLine": "Exalted Orb", "baseType": "Exalted Orb",
                "rarity": "Currency", "identified": True, "corrupted": False,
                "icon": CURRENCY_ICONS.get("Exalted Orb"),
            },
            {
                "id": f"{tab_id_currency}-alt",
                "verified": True, "w": 1, "h": 1, "x": 3, "y": 0,
                "stackSize": 120, "maxStackSize": 5000,
                "typeLine": "Orb of Alteration", "baseType": "Orb of Alteration",
                "rarity": "Currency", "identified": True, "corrupted": False,
                "icon": CURRENCY_ICONS.get("Orb of Alteration"),
            },
            {
                "id": f"{tab_id_currency}-alchemy",
                "verified": True, "w": 1, "h": 1, "x": 4, "y": 0,
                "stackSize": 55, "maxStackSize": 5000,
                "typeLine": "Orb of Alchemy", "baseType": "Orb of Alchemy",
                "rarity": "Currency", "identified": True, "corrupted": False,
                "icon": CURRENCY_ICONS.get("Orb of Alchemy"),
            },
            {
                "id": f"{tab_id_currency}-vaal",
                "verified": True, "w": 1, "h": 1, "x": 5, "y": 0,
                "stackSize": 33, "maxStackSize": 20,
                "typeLine": "Vaal Orb", "baseType": "Vaal Orb",
                "rarity": "Currency", "identified": True, "corrupted": False,
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
                tab_id_dump:     {"items": packed_all},
                tab_id_currency: {"items": currency_items},
                tab_id_new:      {"items": pack_items(list(new_items))},
            },
            # prev_contents: what mock-ggg returns on the FIRST call to each tab.
            # Differs from contents so the activity log detects changes on 2nd refresh.
            "prev_contents": {
                tab_id_dump:     {"items": packed_prev},
                tab_id_currency: {"items": currency_items},  # currency unchanged
                tab_id_new:      {"items": []},              # "New Loot" was empty
            },
        }

    return all_stashes


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

    # ── Generate stashes.json from character items ─────────────────────────────
    print("\nGenerating stashes.json from character items …")
    char_names = list(SAMPLES_MAP.keys())
    leagues = {
        "Fate of the Vaal":         char_names,
        "Dawn of the Hunt":         char_names[:2],  # smaller set for the old league
    }
    stashes = build_stashes(leagues)

    for league, data in stashes.items():
        dump_count = len(data["contents"].get(list(data["contents"].keys())[0], {}).get("items", []))
        prev_count = len(data["prev_contents"].get(list(data["prev_contents"].keys())[0], {}).get("items", []))
        print(f"  {league}: gear tab {dump_count} items (prev: {prev_count})")

    (FIXTURES / "stashes.json").write_text(
        json.dumps(stashes, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print("Wrote fixtures/stashes.json")
    print("\nDone.")


if __name__ == "__main__":
    main()
