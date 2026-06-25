"""Character domain model."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.domain.item import Item, parse_item, resolve_item_inventory_id
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
    gems: list[Item] = Field(default_factory=list)
    jewels: list[Item] = Field(default_factory=list)
    inventory: list[Item] = Field(default_factory=list)
    # Cumulative mod rollups; see :mod:`app.domain.stat_summary`.
    stat_summary: EquipmentStatSummary = Field(default_factory=EquipmentStatSummary)


_EQUIPPED_SLOTS = {
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

_GEM_SLOTS = {"SkillSlots", "AscendancySkills", "DefaultAttackSkills"}
_JEWEL_SLOTS = {"PassiveJewels"}


def _expand_nested_item_dicts(raw: object) -> list[dict[str, Any]]:
    """Walk skill-gem trees (``allGems``, ``socketedItems``) from live or poe.ninja payloads."""
    if not isinstance(raw, dict):
        return []
    out: list[dict[str, Any]] = [raw]
    for key in ("allGems", "socketedItems"):
        for child in raw.get(key) or []:
            out.extend(_expand_nested_item_dicts(child))
    return out


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
        for key in ("equipment", "inventory", "rucksack", "jewels"):
            for raw in char.get(key) or []:
                add(raw)
        for raw in char.get("skills") or []:
            for expanded in _expand_nested_item_dicts(raw):
                add(expanded)

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
    gems: list[Item] = []
    jewels: list[Item] = []
    inventory: list[Item] = []
    for raw in collect_character_items(payload):
        if not isinstance(raw, dict):
            continue
        item = parse_item(raw)
        iid = resolve_item_inventory_id(raw) or item.inventory_id
        if iid and item.inventory_id != iid:
            item = item.model_copy(update={"inventory_id": iid})
        if iid in _EQUIPPED_SLOTS:
            equipped.append(item)
        elif iid in _GEM_SLOTS:
            gems.append(item)
        elif iid in _JEWEL_SLOTS:
            jewels.append(item)
        else:
            inventory.append(item)
    return CharacterDetail(
        summary=summary,
        equipped=equipped,
        gems=gems,
        jewels=jewels,
        inventory=inventory,
        stat_summary=summarize_equipment(equipped),
    )
