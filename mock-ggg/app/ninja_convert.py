"""Convert poe.ninja charModel / exports to GGG account API character shape.

Used by mock-ggg live fetch and by ``samples/convert.py`` for fixture regeneration.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

FRAME_TO_RARITY = {
    0: "Normal",
    1: "Magic",
    2: "Rare",
    3: "Unique",
    4: "Gem",
    5: "Currency",
    6: "Quest",
    9: "Relic",
}

_STRIP = frozenset({
    "doubleCorrupted",
    "desecrated",
    "desecratedMods",
    "bondedMods",
    "grantedSkills",
    "runeMods",
    "support",
    "gemTabs",
    "gemSkill",
    "gemBackground",
    "weaponRequirements",
    "supportGemRequirements",
    "gemSockets",
    "iconTierText",
    "qualityProperty",
    "artFilename",
    "mutatedMods",
    "mutated",
    "scourgeMods",
    "crucibleMods",
    "fracturedMods",
    "additionalProperties",
    "descrText",
    "secDescrText",
    "prophecyText",
    "note",
    "flavourText",
    "extended",
    "duplicated",
    "synthesised",
    "fractured",
    "replica",
    "stackSize",
})

CURRENCY_ICONS: dict[str, str] = {
    "Divine Orb": "https://web.poecdn.com/gen/image/WzI1LDE0LHsiZiI6IjJESXRlbXMvQ3VycmVuY3kvQ3VycmVuY3lNb2RWYWx1ZXMiLCJ3IjoxLCJoIjoxLCJzY2FsZSI6MX1d/e1a54ff97d/CurrencyModValues.png",
    "Chaos Orb": "https://web.poecdn.com/gen/image/WzI1LDE0LHsiZiI6IjJESXRlbXMvQ3VycmVuY3kvQ3VycmVuY3lSZXJvbGxSYXJlIiwidyI6MSwiaCI6MSwic2NhbGUiOjF9XQ/d119a0d734/CurrencyRerollRare.png",
    "Exalted Orb": "https://web.poecdn.com/gen/image/WzI1LDE0LHsiZiI6IjJESXRlbXMvQ3VycmVuY3kvQ3VycmVuY3lBZGRNb2RUb1JhcmUiLCJ3IjoxLCJoIjoxLCJzY2FsZSI6MX1d/1e4a9c1e1d/CurrencyAddModToRare.png",
    "Orb of Alteration": "https://web.poecdn.com/gen/image/WzI1LDE0LHsiZiI6IjJESXRlbXMvQ3VycmVuY3kvQ3VycmVuY3lSZXJvbGxNYWdpYyIsInciOjEsImgiOjEsInNjYWxlIjoxfV0=/85fff943e6/CurrencyRerollMagic.png",
    "Orb of Alchemy": "https://web.poecdn.com/gen/image/WzI1LDE0LHsiZiI6IjJESXRlbXMvQ3VycmVuY3kvQ3VycmVuY3lVcGdyYWRlVG9SYXJlIiwidyI6MSwiaCI6MSwic2NhbGUiOjF9XQ/667f4e9745/CurrencyUpgradeToRare.png",
    "Orb of Transmutation": "https://web.poecdn.com/gen/image/WzI1LDE0LHsiZiI6IjJESXRlbXMvQ3VycmVuY3kvQ3VycmVuY3lVcGdyYWRlVG9NYWdpYyIsInciOjEsImgiOjEsInNjYWxlIjoxfV0=/1b6ace67e5/CurrencyUpgradeToMagic.png",
    "Vaal Orb": "https://web.poecdn.com/gen/image/WzI1LDE0LHsiZiI6IjJESXRlbXMvQ3VycmVuY3kvQ3VycmVuY3lWYWFsIiwidyI6MSwiaCI6MSwic2NhbGUiOjF9XQ/4e04497800/CurrencyVaal.png",
}


def stable_id(name: str) -> str:
    h = hashlib.sha256(name.encode()).hexdigest()
    return f"{h[:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:32]}"


def convert_item_data(raw: dict, *, depth: int = 0) -> dict:
    item = raw.copy()
    item.setdefault("verified", True)
    item.setdefault("identified", True)
    item.setdefault("corrupted", False)
    if not item.get("rarity"):
        item["rarity"] = FRAME_TO_RARITY.get(item.get("frameType", 0), "Normal")
    raw_socketed = item.pop("socketedItems", None) or []
    if depth == 0:
        item["socketedItems"] = [
            convert_item_data(si, depth=1) for si in raw_socketed if isinstance(si, dict)
        ]
    for key in _STRIP:
        item.pop(key, None)
    return item


def convert_item(wrapped: dict) -> dict:
    return convert_item_data(wrapped["itemData"])


def pack_items(items: list[dict], grid_w: int = 12, grid_h: int = 12) -> list[dict]:
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


def char_model_to_ggg_payload(cm: dict[str, Any], *, id_key: str | None = None) -> dict[str, Any]:
    """GGG-shaped ``{"character": ..., "items": ...}`` from a poe.ninja ``charModel`` dict."""
    name = str(cm["name"])
    key = id_key if id_key is not None else name
    character = {
        "id": stable_id(key),
        "name": name,
        "realm": "pc",
        "class": cm["class"],
        "level": cm["level"],
        "league": cm["league"],
        "experience": 0,
    }
    gear = [convert_item(raw) for raw in cm.get("items", []) or []]
    jewels = [convert_item(raw) for raw in cm.get("jewels", []) or []]
    return {"character": character, "items": gear + jewels}


def ninja_model_body_to_ggg(body: dict[str, Any]) -> dict[str, Any]:
    """Parse poe.ninja ``/model/{version}`` JSON (expects ``charModel``)."""
    cm = body.get("charModel")
    if not isinstance(cm, dict):
        raise ValueError("missing_char_model")
    return char_model_to_ggg_payload(cm)


def convert_character_file(path: Path, char_name: str) -> dict[str, Any]:
    import json

    data = json.loads(path.read_text(encoding="utf-8"))
    cm = data["charModel"]
    return char_model_to_ggg_payload(cm, id_key=char_name)
