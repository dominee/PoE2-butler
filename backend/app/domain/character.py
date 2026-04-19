"""Character domain model."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.domain.item import Item, parse_item


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
    for raw in payload.get("items", []) or []:
        if not isinstance(raw, dict):
            continue
        item = parse_item(raw)
        if item.inventory_id in _INVENTORY_SLOTS:
            equipped.append(item)
        else:
            inventory.append(item)
    return CharacterDetail(summary=summary, equipped=equipped, inventory=inventory)
