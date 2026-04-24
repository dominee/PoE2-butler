"""Normalized item model.

Produced from the raw GGG item JSON.  Kept compact and frontend-friendly.
"""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from app.services import mod_db as _mod_db
from app.services import unique_reference as _unique_ref

# ── tag stripping ─────────────────────────────────────────────────────────────
# GGG item data encodes display tags as [Id|Label] or [Id].
# Strip them to plain text (same logic lives in frontend/src/utils/modText.ts).
_TAG_LABELED = re.compile(r"\[([^\]|]+)\|([^\]]+)\]")
_TAG_PLAIN = re.compile(r"\[([^\]]+)\]")


def _strip_tags(text: str) -> str:
    return _TAG_PLAIN.sub(lambda m: m.group(1), _TAG_LABELED.sub(lambda m: m.group(2), text))


def _unwrap_ggg_item_dict(raw: dict[str, Any]) -> dict[str, Any]:
    """Path of Exile 2 character payloads often put the item under ``itemData``; flavour and
    ``extended`` live there while ``inventoryId`` / slot metadata stay on the outer object."""
    inner = raw.get("itemData")
    if not isinstance(inner, dict):
        return raw
    out: dict[str, Any] = {**inner}
    for k, v in raw.items():
        if k == "itemData" or v is None:
            continue
        if k not in out or out[k] in (None, "", []):
            out[k] = v
    return out


def _flavour_text_from_dict(raw: dict[str, Any]) -> str | None:
    for key in ("flavourText", "flavorText"):
        fl_raw = raw.get(key)
        if isinstance(fl_raw, list):
            return "\n".join(_strip_tags(str(x)) for x in fl_raw) or None
        if isinstance(fl_raw, str) and fl_raw.strip():
            return _strip_tags(fl_raw) or None
    return None


def _reference_range_for_mod_line(
    mod: str, hints: list[dict[str, str]]
) -> str | None:
    """Pick a wiki-style range string; longest ``when_contains`` match wins (after tag strip)."""
    if not mod.strip() or not hints:
        return None
    line = _strip_tags(mod).lower()
    best: str | None = None
    best_w = 0
    for h in sorted(hints, key=lambda d: -len(d.get("when_contains", ""))):
        w = h.get("when_contains", "").lower().strip()
        r = (h.get("range") or "").strip()
        if w and r and w in line and len(w) > best_w:
            best = r
            best_w = len(w)
    return best


def _reference_range_columns(
    mods: list[str], hints: list[dict[str, str]]
) -> list[str | None]:
    return [_reference_range_for_mod_line(m, hints) for m in mods]


class ItemProperty(BaseModel):
    name: str
    value: str | None = None

    @classmethod
    def from_ggg(cls, raw: dict[str, Any]) -> ItemProperty:
        name = _strip_tags(str(raw.get("name", "")))
        values = raw.get("values") or []
        value = None
        if values and isinstance(values[0], list) and values[0]:
            value = str(values[0][0])
        return cls(name=name, value=value)


class Socket(BaseModel):
    group: int = 0
    type: str = ""


class ModMagnitude(BaseModel):
    """Single stat range entry from GGG extended mod data."""

    hash: str = ""
    min: float | None = None
    max: float | None = None
    t1_max: float | None = None  # from bundled mod DB; None = unknown


class ModDetail(BaseModel):
    """Per-modifier metadata from GGG ``extended.mods`` — present only when
    the GGG API returns the *extended* object (not all endpoints do)."""

    name: str = ""
    tier: int | None = None  # 1 = T1 (best), None when unknown
    level: int | None = None
    magnitudes: list[ModMagnitude] = Field(default_factory=list)


class Item(BaseModel):
    id: str
    inventory_id: str | None = None
    w: int = 1
    h: int = 1
    x: int | None = None
    y: int | None = None
    item_class: str | None = None
    name: str = ""
    type_line: str = ""
    base_type: str = ""
    rarity: str = "Normal"
    ilvl: int | None = None
    identified: bool = True
    corrupted: bool = False
    flavour_text: str | None = None
    implicit_mod_range_hints: list[str | None] = Field(
        default_factory=list,
        description="Wiki/match per implicit line; parallel to implicit_mods.",
    )
    explicit_mod_range_hints: list[str | None] = Field(
        default_factory=list,
        description="Wiki/match per explicit line; parallel to explicit_mods.",
    )
    trailer_note: str | None = None
    properties: list[ItemProperty] = Field(default_factory=list)
    requirements: list[ItemProperty] = Field(default_factory=list)
    implicit_mods: list[str] = Field(default_factory=list)
    implicit_mod_details: list[ModDetail] = Field(default_factory=list)
    explicit_mods: list[str] = Field(default_factory=list)
    explicit_mod_details: list[ModDetail] = Field(default_factory=list)
    rune_mods: list[str] = Field(default_factory=list)
    enchant_mods: list[str] = Field(default_factory=list)
    crafted_mods: list[str] = Field(default_factory=list)
    sockets: list[Socket] = Field(default_factory=list)
    socketed_items: list[Item] = Field(default_factory=list)
    stack_size: int | None = None
    max_stack_size: int | None = None
    icon: str | None = None
    raw: dict[str, Any] | None = None


_TIER_RE = re.compile(r"\d+")


def _parse_mod_group(mods: dict[str, Any], key: str) -> list[ModDetail]:  # noqa: PLR0912
    details: list[ModDetail] = []
    for raw_mod in mods.get(key) or []:
        if not isinstance(raw_mod, dict):
            continue
        tier: int | None = None
        tier_raw = raw_mod.get("tier")
        if tier_raw is not None:
            try:
                tier = int(tier_raw)
            except (ValueError, TypeError):
                m = _TIER_RE.search(str(tier_raw))
                if m:
                    tier = int(m.group())
        magnitudes = []
        for mag in raw_mod.get("magnitudes") or []:
            if not isinstance(mag, dict):
                continue
            stat_hash = str(mag.get("hash", ""))
            magnitudes.append(
                ModMagnitude(
                    hash=stat_hash,
                    min=mag.get("min"),
                    max=mag.get("max"),
                    t1_max=_mod_db.get_t1_max(stat_hash) if stat_hash else None,
                )
            )
        details.append(
            ModDetail(
                name=str(raw_mod.get("name", "")),
                tier=tier,
                level=raw_mod.get("level"),
                magnitudes=magnitudes,
            )
        )
    return details


def _parse_mod_details_from_extended(
    extended: dict[str, Any] | None,
) -> tuple[list[ModDetail], list[ModDetail]]:
    if not isinstance(extended, dict):
        return ([], [])
    mods = extended.get("mods")
    if not isinstance(mods, dict):
        return ([], [])
    return (
        _parse_mod_group(mods, "implicit"),
        _parse_mod_group(mods, "explicit"),
    )


def coerce_item_dict(raw: dict[str, Any]) -> Item:
    """Build an :class:`Item` from either our API JSON (snake_case) or a GGG stash item dict.

    Used for public share create/read so the SPA can POST normalized items while tests and
    bots may still send raw GGG-shaped payloads.
    """
    try:
        return Item.model_validate(raw)
    except ValidationError:
        return parse_item(raw)


def parse_item(raw: dict[str, Any]) -> Item:
    """Convert a GGG item dict into an :class:`Item`."""
    raw = _unwrap_ggg_item_dict(raw)
    props = [ItemProperty.from_ggg(p) for p in raw.get("properties", []) or []]
    reqs = [ItemProperty.from_ggg(p) for p in raw.get("requirements", []) or []]
    sockets = [
        Socket(group=int(s.get("group", 0)), type=str(s.get("type", "")))
        for s in raw.get("sockets", []) or []
        if isinstance(s, dict)
    ]
    extended = raw.get("extended")
    ext: dict[str, Any] = extended if isinstance(extended, dict) else {}
    item_class: str | None = ext.get("category") if isinstance(ext.get("category"), str) else None

    flavour_text = _flavour_text_from_dict(raw)
    rarity = str(raw.get("rarity") or _infer_rarity(raw))
    name = str(raw.get("name", ""))
    base_type = str(raw.get("baseType", raw.get("typeLine", "")))
    mod_range_hints: list[dict[str, str]] = []
    if rarity == "Unique" and name.strip() and base_type.strip():
        uref = _unique_ref.lookup_unique_reference(name=name, base_type=base_type)
        if uref is not None:
            if (not (flavour_text and flavour_text.strip())) and uref.get("flavour"):
                flavour_text = (uref["flavour"] or "").strip() or None
            raw_hints = uref.get("mod_range_hints")
            if isinstance(raw_hints, list):
                mod_range_hints = [h for h in raw_hints if isinstance(h, dict)]

    implicit_mod_details, explicit_mod_details = _parse_mod_details_from_extended(ext)
    implicit_mods_list = list(raw.get("implicitMods") or [])
    explicit_mods_list = list(raw.get("explicitMods") or [])
    implicit_mod_range_hints = (
        _reference_range_columns([str(m) for m in implicit_mods_list], mod_range_hints)
        if mod_range_hints
        else []
    )
    explicit_mod_range_hints = (
        _reference_range_columns([str(m) for m in explicit_mods_list], mod_range_hints)
        if mod_range_hints
        else []
    )
    socketed_items = [
        parse_item(si) for si in (raw.get("socketedItems") or []) if isinstance(si, dict)
    ]

    return Item(
        id=str(raw.get("id", "")) or str(raw.get("name", "")),
        inventory_id=raw.get("inventoryId"),
        w=int(raw.get("w", 1)),
        h=int(raw.get("h", 1)),
        x=raw.get("x"),
        y=raw.get("y"),
        item_class=item_class,
        name=str(raw.get("name", "")),
        type_line=str(raw.get("typeLine", "")),
        base_type=str(raw.get("baseType", raw.get("typeLine", ""))),
        rarity=rarity,
        ilvl=raw.get("ilvl"),
        identified=bool(raw.get("identified", True)),
        corrupted=bool(raw.get("corrupted", False)),
        flavour_text=flavour_text,
        properties=props,
        requirements=reqs,
        implicit_mods=implicit_mods_list,
        implicit_mod_details=implicit_mod_details,
        implicit_mod_range_hints=implicit_mod_range_hints,
        explicit_mods=explicit_mods_list,
        explicit_mod_details=explicit_mod_details,
        explicit_mod_range_hints=explicit_mod_range_hints,
        socketed_items=socketed_items,
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
