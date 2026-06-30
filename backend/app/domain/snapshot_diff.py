"""Shared snapshot diff helpers for activity log and character gear timeline."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel

from app.domain.character import collect_character_items
from app.domain.item import Item, _unwrap_ggg_item_dict, parse_item


class ChangedItem(BaseModel):
    old: Item
    new: Item


def items_by_id(payload: dict[str, Any], *, character: bool = False) -> dict[str, dict[str, Any]]:
    raw_items = collect_character_items(payload) if character else payload.get("items") or []
    out: dict[str, dict[str, Any]] = {}
    for raw in raw_items:
        if not isinstance(raw, dict):
            continue
        normalized = _unwrap_ggg_item_dict(raw) if character else raw
        iid = normalized.get("id")
        if iid:
            out[str(iid)] = normalized
    return out


_CHANGE_KEYS = ("explicitMods", "implicitMods", "craftedMods", "enchantMods", "runeMods")


def item_changed(old: dict[str, Any], new: dict[str, Any]) -> bool:
    for k in _CHANGE_KEYS:
        if old.get(k) != new.get(k):
            return True
    old_props = [(p.get("name"), p.get("values")) for p in (old.get("properties") or [])]
    new_props = [(p.get("name"), p.get("values")) for p in (new.get("properties") or [])]
    return old_props != new_props


def diff_payloads(
    old_p: dict[str, Any],
    new_p: dict[str, Any],
    *,
    character: bool = False,
) -> tuple[list[Item], list[ChangedItem], list[Item]]:
    old_map = items_by_id(old_p, character=character)
    new_map = items_by_id(new_p, character=character)

    new_items = [parse_item(v) for k, v in new_map.items() if k not in old_map]
    removed = [parse_item(v) for k, v in old_map.items() if k not in new_map]
    changed = [
        ChangedItem(old=parse_item(old_map[k]), new=parse_item(v))
        for k, v in new_map.items()
        if k in old_map and item_changed(old_map[k], v)
    ]
    return new_items, changed, removed


def character_gear_changed(old_p: dict[str, Any], new_p: dict[str, Any]) -> bool:
    new_items, changed, removed = diff_payloads(old_p, new_p, character=True)
    return bool(new_items or changed or removed)


class CharacterSnapshotChangeLine(BaseModel):
    kind: Literal["new", "changed", "removed"]
    label: str


def _item_label(item: Item) -> str:
    return item.name or item.base_type or item.type_line or "Item"


def summarize_character_changes(
    old_p: dict[str, Any],
    new_p: dict[str, Any],
) -> list[CharacterSnapshotChangeLine]:
    new_items, changed, removed = diff_payloads(old_p, new_p, character=True)
    lines: list[CharacterSnapshotChangeLine] = []
    for item in new_items:
        lines.append(CharacterSnapshotChangeLine(kind="new", label=_item_label(item)))
    for pair in changed:
        lines.append(CharacterSnapshotChangeLine(kind="changed", label=_item_label(pair.new)))
    for item in removed:
        lines.append(CharacterSnapshotChangeLine(kind="removed", label=_item_label(item)))
    return lines
