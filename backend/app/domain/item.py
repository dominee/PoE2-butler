"""Normalized item model.

Produced from the raw GGG item JSON.  Kept compact and frontend-friendly.
More precise mod typing (implicit / rune / enchant) arrives in M2 together
with the trade URL builder; M1 only needs the shape to render an item card.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ItemProperty(BaseModel):
    name: str
    value: str | None = None

    @classmethod
    def from_ggg(cls, raw: dict[str, Any]) -> ItemProperty:
        name = str(raw.get("name", ""))
        values = raw.get("values") or []
        value = None
        if values and isinstance(values[0], list) and values[0]:
            value = str(values[0][0])
        return cls(name=name, value=value)


class Socket(BaseModel):
    group: int = 0
    type: str = ""


class Item(BaseModel):
    id: str
    inventory_id: str | None = None
    w: int = 1
    h: int = 1
    x: int | None = None
    y: int | None = None
    name: str = ""
    type_line: str = ""
    base_type: str = ""
    rarity: str = "Normal"
    ilvl: int | None = None
    identified: bool = True
    corrupted: bool = False
    properties: list[ItemProperty] = Field(default_factory=list)
    requirements: list[ItemProperty] = Field(default_factory=list)
    implicit_mods: list[str] = Field(default_factory=list)
    explicit_mods: list[str] = Field(default_factory=list)
    rune_mods: list[str] = Field(default_factory=list)
    enchant_mods: list[str] = Field(default_factory=list)
    crafted_mods: list[str] = Field(default_factory=list)
    sockets: list[Socket] = Field(default_factory=list)
    stack_size: int | None = None
    max_stack_size: int | None = None
    icon: str | None = None
    raw: dict[str, Any] | None = None


def parse_item(raw: dict[str, Any]) -> Item:
    """Convert a GGG item dict into an :class:`Item`."""
    props = [ItemProperty.from_ggg(p) for p in raw.get("properties", []) or []]
    reqs = [ItemProperty.from_ggg(p) for p in raw.get("requirements", []) or []]
    sockets = [
        Socket(group=int(s.get("group", 0)), type=str(s.get("type", "")))
        for s in raw.get("sockets", []) or []
        if isinstance(s, dict)
    ]

    return Item(
        id=str(raw.get("id", "")) or str(raw.get("name", "")),
        inventory_id=raw.get("inventoryId"),
        w=int(raw.get("w", 1)),
        h=int(raw.get("h", 1)),
        x=raw.get("x"),
        y=raw.get("y"),
        name=str(raw.get("name", "")),
        type_line=str(raw.get("typeLine", "")),
        base_type=str(raw.get("baseType", raw.get("typeLine", ""))),
        rarity=str(raw.get("rarity") or _infer_rarity(raw)),
        ilvl=raw.get("ilvl"),
        identified=bool(raw.get("identified", True)),
        corrupted=bool(raw.get("corrupted", False)),
        properties=props,
        requirements=reqs,
        implicit_mods=list(raw.get("implicitMods") or []),
        explicit_mods=list(raw.get("explicitMods") or []),
        rune_mods=list(raw.get("runeMods") or []),
        enchant_mods=list(raw.get("enchantMods") or []),
        crafted_mods=list(raw.get("craftedMods") or []),
        sockets=sockets,
        stack_size=raw.get("stackSize"),
        max_stack_size=raw.get("maxStackSize"),
        icon=raw.get("icon"),
        raw=None,
    )


_FRAME_TO_RARITY = {
    0: "Normal",
    1: "Magic",
    2: "Rare",
    3: "Unique",
    4: "Gem",
    5: "Currency",
    6: "DivinationCard",
    7: "QuestItem",
}


def _infer_rarity(raw: dict[str, Any]) -> str:
    frame = raw.get("frameType")
    if isinstance(frame, int):
        return _FRAME_TO_RARITY.get(frame, "Normal")
    return "Normal"
