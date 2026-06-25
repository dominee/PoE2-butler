"""Character domain model."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.domain.item import Item, parse_item
from app.domain.stat_summary import EquipmentStatSummary, summarize_equipment


class CharacterSummary(BaseModel):
    id: str
    name: str
    realm: str = "pc"
    character_class: str = Field(alias="class")
    level: int = 0
    league: str | None = None
    experience: int | None = None

    model_config = {"populate_by_name": True}


class CharacterDetail(BaseModel):
    summary: CharacterSummary
    equipped: list[Item] = Field(default_factory=list)
    inventory: list[Item] = Field(default_factory=list)
    # Cumulative mod rollups; see :mod:`app.domain.stat_summary`.
    stat_summary: EquipmentStatSummary = Field(default_factory=EquipmentStatSummary)


_INVENTORY_SLOTS = {
    "Weapon",
    "Weapon2",
    "Offhand",
    "Offhand2",
    "Helm",
    "BodyArmour",
    "Gloves",
    "Boots",
    "Amulet",
    "Ring",
    "Ring2",
    "Belt",
    "Flask",
}


def collect_character_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Flatten item dicts from GGG character detail JSON (PoE1, PoE2, and mock shapes).

    Live PoE2 OAuth returns gear under ``character.equipment`` (and ``character.skills``);
    mock / Poe.ninja fixtures use a top-level ``items`` array; PoE1 may use ``inventory``.
    """
    out: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add(raw: object) -> None:
        if not isinstance(raw, dict):
            return
        inner = raw.get("itemData")
        iid = str(
            raw.get("id")
            or (inner.get("id") if isinstance(inner, dict) else None)
            or ""
        ).strip()
        if iid:
            if iid in seen:
                return
            seen.add(iid)
        out.append(raw)

    for raw in payload.get("items") or []:
        add(raw)
    for raw in payload.get("equipment") or []:
        add(raw)

    char = payload.get("character")
    if isinstance(char, dict):
        for key in ("equipment", "inventory", "rucksack", "jewels", "skills"):
            for raw in char.get(key) or []:
                add(raw)

    return out


def parse_summaries(payload: dict[str, Any]) -> list[CharacterSummary]:
    raw = payload.get("characters") or []
    out: list[CharacterSummary] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        out.append(
            CharacterSummary(
                id=str(entry.get("id") or entry.get("name") or ""),
                name=str(entry.get("name", "")),
                realm=str(entry.get("realm", "pc")),
                **{"class": str(entry.get("class", ""))},
                level=int(entry.get("level", 0)),
                league=entry.get("league"),
                experience=entry.get("experience"),
            )
        )
    return out


def parse_detail(payload: dict[str, Any]) -> CharacterDetail:
    char = payload.get("character") or {}
    summary = CharacterSummary(
        id=str(char.get("id") or char.get("name") or ""),
        name=str(char.get("name", "")),
        realm=str(char.get("realm", "pc")),
        **{"class": str(char.get("class", ""))},
        level=int(char.get("level", 0)),
        league=char.get("league"),
        experience=char.get("experience"),
    )
    equipped: list[Item] = []
    inventory: list[Item] = []
    for raw in collect_character_items(payload):
        if not isinstance(raw, dict):
            continue
        item = parse_item(raw)
        if item.inventory_id in _INVENTORY_SLOTS:
            equipped.append(item)
        else:
            inventory.append(item)
    return CharacterDetail(
        summary=summary,
        equipped=equipped,
        inventory=inventory,
        stat_summary=summarize_equipment(equipped),
    )
