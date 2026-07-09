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


def strip_item_mod_text(text: str) -> str:
    """Strip GGG ``[Id|Label]`` markup from a mod line (inventory / trade / export)."""
    return _strip_tags(text)


# Poe.ninja / live GGG character payloads may expose slot as numeric ``itemSlot`` only.
_GGG_ITEM_SLOT_TO_INVENTORY_ID: dict[int, str] = {
    1: "Helm",
    2: "Gloves",
    3: "BodyArmour",
    4: "Amulet",
    5: "Boots",
    6: "Offhand",
    7: "Weapon",
    8: "Ring",
    9: "Ring2",
    11: "Belt",
    12: "PassiveJewels",
    14: "Flask",
    15: "Weapon2",
    16: "Offhand2",
}


def _inventory_id_from_item_slot(slot: object) -> str | None:
    if isinstance(slot, int):
        return _GGG_ITEM_SLOT_TO_INVENTORY_ID.get(slot)
    if isinstance(slot, str) and slot.isdigit():
        return _GGG_ITEM_SLOT_TO_INVENTORY_ID.get(int(slot))
    return None


def _normalize_inventory_id(raw: dict[str, Any]) -> str | None:
    """Resolve slot name from a flat or merged item dict (no wrapper precedence)."""
    mapped = _inventory_id_from_item_slot(raw.get("itemSlot"))
    if mapped:
        return mapped
    iid = raw.get("inventoryId")
    if isinstance(iid, str) and iid.strip():
        return iid.strip()
    return _inventory_id_from_item_slot(iid)


def resolve_item_inventory_id(raw: dict[str, Any]) -> str | None:
    """Resolve ``inventoryId`` / slot for a raw GGG or poe.ninja character row.

    Works on flat items and ``{ itemData, itemSlot?, inventoryId? }`` wrappers.
    Live PoE2 often puts ``itemSlot`` on the wrapper while ``itemData.inventoryId``
    is missing or stale — without this, only rows with outer ``inventoryId`` (often
    just the weapon) classify as equipped gear.
    """
    if not isinstance(raw, dict):
        return None
    inner = raw.get("itemData")
    if isinstance(inner, dict):
        merged: dict[str, Any] = {**inner}
        for k, v in raw.items():
            if k == "itemData" or v is None:
                continue
            if k not in merged or merged[k] in (None, "", []):
                merged[k] = v
        return _resolve_inventory_id(raw, merged)
    return _normalize_inventory_id(raw)


def _resolve_inventory_id(wrapper: dict[str, Any], merged: dict[str, Any]) -> str | None:
    """Pick the equipment slot for a wrapped GGG character item.

    Live PoE2 payloads keep authoritative slot metadata on the wrapper
    (``inventoryId`` or numeric ``itemSlot``) while ``itemData.inventoryId`` is
    often stale (e.g. ``SkillSlots`` on armour). Wrapper metadata must win.
    """
    outer_iid = wrapper.get("inventoryId")
    if isinstance(outer_iid, str) and outer_iid.strip():
        return outer_iid.strip()
    outer_slot = _inventory_id_from_item_slot(wrapper.get("itemSlot"))
    if outer_slot:
        return outer_slot
    return _normalize_inventory_id(merged)


_EQUIPMENT_INVENTORY_IDS = frozenset(
    {
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
    }
)


def _looks_like_gem_art(url: str) -> bool:
    u = url.lower()
    return (
        "/gems/" in u
        or "skillgem" in u
        or "supportgem" in u
        or "blankgem" in u
        or "gemhover" in u
    )


def _resolve_item_icon(raw: dict[str, Any], merged: dict[str, Any]) -> str | None:
    """Pick item art; ignore stale skill-gem icons on equipment wrappers."""
    inner = raw.get("itemData")
    inner_icon = inner.get("icon") if isinstance(inner, dict) else None
    if isinstance(inner_icon, str) and inner_icon.strip():
        return inner_icon.strip()
    wrap_icon = raw.get("icon")
    if not isinstance(wrap_icon, str) or not wrap_icon.strip():
        return None
    slot = _resolve_inventory_id(raw, merged) or merged.get("inventoryId")
    if (
        isinstance(slot, str)
        and slot in _EQUIPMENT_INVENTORY_IDS
        and _looks_like_gem_art(wrap_icon)
    ):
        return None
    return wrap_icon.strip()


def _unwrap_ggg_item_dict(raw: dict[str, Any]) -> dict[str, Any]:
    """Path of Exile 2 character payloads often put the item under ``itemData``; flavour and
    ``extended`` live there while ``inventoryId`` / slot metadata stay on the outer object."""
    inner = raw.get("itemData")
    if not isinstance(inner, dict):
        out = dict(raw)
        resolved = _normalize_inventory_id(out)
        if resolved:
            out["inventoryId"] = resolved
        return out
    out: dict[str, Any] = {**inner}
    for k, v in raw.items():
        if k == "itemData" or v is None:
            continue
        if k not in out or out[k] in (None, "", []):
            out[k] = v
    resolved = _resolve_inventory_id(raw, out)
    if resolved:
        out["inventoryId"] = resolved
    icon = _resolve_item_icon(raw, out)
    if icon:
        out["icon"] = icon
    elif "icon" in out:
        out.pop("icon", None)
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


_GRANTS_SKILL_LABEL = "grants skill"
_GRANTED_SKILL_LEVEL_RE = re.compile(r"^Level\s+(\d+)\s+(.+)$", re.IGNORECASE)


def format_granted_skill_display(raw_value: str) -> str:
    """Format GGG granted-skill text as ``Skill Name (lvl N)``."""
    text = _strip_tags(raw_value.strip())
    if not text:
        return ""
    match = _GRANTED_SKILL_LEVEL_RE.match(text)
    if match:
        level, skill = match.group(1), match.group(2).strip()
        return f"{skill} (lvl {level})"
    return text


def _granted_skill_from_property(prop: ItemProperty) -> str | None:
    if _strip_tags(prop.name).strip().casefold() != _GRANTS_SKILL_LABEL:
        return None
    if prop.value is None or not str(prop.value).strip():
        return None
    formatted = format_granted_skill_display(str(prop.value))
    return formatted or None


def _parse_granted_skills_from_raw(raw: dict[str, Any]) -> list[str]:
    skills: list[str] = []
    seen: set[str] = set()
    for gs in raw.get("grantedSkills") or []:
        if not isinstance(gs, dict):
            continue
        for entry in gs.get("values") or []:
            if isinstance(entry, list) and entry:
                formatted = format_granted_skill_display(str(entry[0]))
                if formatted and formatted not in seen:
                    seen.add(formatted)
                    skills.append(formatted)
    return skills


def _split_properties_and_granted_skills(
    props: list[ItemProperty],
) -> tuple[list[ItemProperty], list[str]]:
    remaining: list[ItemProperty] = []
    from_props: list[str] = []
    seen: set[str] = set()
    for prop in props:
        skill = _granted_skill_from_property(prop)
        if skill:
            if skill not in seen:
                seen.add(skill)
                from_props.append(skill)
            continue
        remaining.append(prop)
    return remaining, from_props


def _merge_granted_skill_lists(primary: list[str], secondary: list[str]) -> list[str]:
    """Prefer entries from ``primary`` (GGG ``grantedSkills``) when both exist."""
    if primary:
        return primary
    return secondary


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
    # All tiers for this mod family, T1-first, from the bundled RePoE DB.
    # Each entry: {tier_ggg, required_level, name, stats: [{id, min, max}]}.
    # None when the mod name is not in the DB; empty list when the DB has no
    # entry for this name.
    all_tiers: list[dict[str, Any]] | None = None


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
    double_corrupted: bool = False
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
    granted_skills: list[str] = Field(default_factory=list)
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
    frame_type_id: str | None = None
    runeforged: bool = False
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
        mod_name = str(raw_mod.get("name", ""))
        magnitudes = []
        for mag in raw_mod.get("magnitudes") or []:
            if not isinstance(mag, dict):
                continue
            stat_hash = str(mag.get("hash", ""))
            # Primary lookup: by stat hash (populated by extract_mod_ranges.py).
            t1_max = _mod_db.get_t1_max(stat_hash) if stat_hash else None
            # Fallback: by mod display name (populated by ingest_repoe_mods.py).
            if t1_max is None and mod_name:
                t1_max = _mod_db.get_t1_max_by_name(mod_name)
            magnitudes.append(
                ModMagnitude(
                    hash=stat_hash,
                    min=mag.get("min"),
                    max=mag.get("max"),
                    t1_max=t1_max,
                )
            )
        # Full tier list from the RePoE DB (empty list = DB missing this mod).
        all_tiers = _mod_db.get_tiers_for_mod_name(mod_name) if mod_name else None
        details.append(
            ModDetail(
                name=mod_name,
                tier=tier,
                level=raw_mod.get("level"),
                magnitudes=magnitudes,
                all_tiers=all_tiers if all_tiers else None,
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


# ── text-based mod inference (for items without extended.mods) ───────────────

# Words that carry no discriminative value when matching mod text to mod tags.
_STOP_WORDS: frozenset[str] = frozenset(
    [
        "increased", "decreased", "more", "less", "to", "of", "the", "a",
        "an", "in", "on", "with", "for", "and", "or", "from", "all", "your",
        "you", "while", "when", "if", "this", "have", "has", "be", "are",
        "is", "at", "by", "gain", "gains", "chance", "recently", "per",
        "each", "every", "global", "local", "base", "maximum", "minimum",
        "additional", "during", "effect", "item", "found", "taken", "dealt",
        "nearby", "enemies", "enemy", "ally", "allies", "hit", "hits",
        "also", "not", "been", "over", "through", "has", "as",
    ]
)


def _mod_text_keywords(text: str) -> tuple[list[str], bool]:
    """Extract distinctive lowercase keywords and percent flag from mod text.

    Returns ``(keywords, is_percent)`` where ``is_percent`` is ``True`` when
    a number is immediately followed by ``%`` in the original text.
    """
    is_percent = bool(re.search(r"\d\s*%", text))
    # Strip numbers and punctuation, lowercase.
    clean = re.sub(r"[-+]?\d+\.?\d*", "", text).lower()
    words = re.findall(r"[a-z]+", clean)
    keywords = [w for w in words if w not in _STOP_WORDS and len(w) > 2]
    return keywords, is_percent


def _infer_mod_detail(mod_text: str, ilvl: int) -> ModDetail | None:
    """Best-effort: synthesise a :class:`ModDetail` from plain mod text.

    Used when ``extended.mods`` is absent (GGG character API items / poe.ninja
    exports).  Matches the primary numeric value against ``mod_groups`` entries
    whose ``implicit_tags`` include the keywords extracted from *mod_text*.

    Returns ``None`` when no sufficiently confident match is found; the caller
    should keep an empty ``ModDetail`` in that case so parallel arrays stay
    aligned.
    """
    # Parse primary numeric value (average for "5 to 12" ranges).
    nums = re.findall(r"[-+]?(\d+\.?\d*)", mod_text)
    if not nums:
        return None
    try:
        value = float(nums[0]) if len(nums) == 1 else (float(nums[0]) + float(nums[1])) / 2
    except ValueError:
        return None

    keywords, is_percent = _mod_text_keywords(_strip_tags(mod_text))
    if not keywords:
        return None

    result = _mod_db.find_group_for_mod(
        value, keywords, is_percent=is_percent, ilvl=ilvl
    )
    if result is None:
        return None

    group_name, all_tiers = result  # noqa: F841

    # Find the specific tier containing the value.
    matched_tier: dict[str, Any] | None = None
    for tier in all_tiers:
        stats = tier.get("stats") or []
        if not stats:
            continue
        primary = stats[0]
        mn: float | None = primary.get("min")
        mx: float | None = primary.get("max")
        if mn is not None and mx is not None and mn <= value <= mx:
            matched_tier = tier
            break

    if matched_tier is None:
        return None

    # T1 is the first entry in all_tiers (T1-first ordering).
    t1_stats = (all_tiers[0].get("stats") or []) if all_tiers else []
    t1_max: float | None = t1_stats[0].get("max") if t1_stats else None

    tier_stats = matched_tier.get("stats") or []
    primary_stat = tier_stats[0] if tier_stats else {}

    return ModDetail(
        name=str(matched_tier.get("name") or ""),
        tier=matched_tier.get("tier_ggg"),
        level=matched_tier.get("required_level"),
        magnitudes=[
            ModMagnitude(
                hash="",
                min=primary_stat.get("min"),
                max=primary_stat.get("max"),
                t1_max=t1_max,
            )
        ],
        all_tiers=all_tiers if all_tiers else None,
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
    props, granted_from_props = _split_properties_and_granted_skills(props)
    granted_skills = _merge_granted_skill_lists(
        _parse_granted_skills_from_raw(raw),
        granted_from_props,
    )
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
    implicit_mods_list = [strip_item_mod_text(str(m)) for m in raw.get("implicitMods") or []]
    explicit_mods_list = [strip_item_mod_text(str(m)) for m in raw.get("explicitMods") or []]

    # For non-Unique items where GGG extended.mods is absent, infer ModDetail
    # entries from plain mod text using the tag_index in mod_ranges.json.
    item_ilvl: int = int(raw.get("ilvl") or 0)
    if rarity != "Unique":
        if not implicit_mod_details and implicit_mods_list:
            implicit_mod_details = [
                _infer_mod_detail(m, item_ilvl) or ModDetail(name="")
                for m in implicit_mods_list
            ]
        if not explicit_mod_details and explicit_mods_list:
            explicit_mod_details = [
                _infer_mod_detail(m, item_ilvl) or ModDetail(name="")
                for m in explicit_mods_list
            ]
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

    base_type = str(raw.get("baseType", raw.get("typeLine", "")))
    frame_type_id = raw.get("frameTypeId")
    frame_type_id_str = (
        str(frame_type_id).strip()
        if isinstance(frame_type_id, str) and frame_type_id.strip()
        else None
    )
    runeforged = _is_runeforged_item(
        base_type=base_type,
        type_line=str(raw.get("typeLine", "")),
        frame_type_id=frame_type_id_str,
        frame_type=raw.get("frameType"),
    )

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
        base_type=base_type,
        rarity=rarity,
        ilvl=raw.get("ilvl"),
        identified=bool(raw.get("identified", True)),
        corrupted=bool(raw.get("corrupted", False)),
        double_corrupted=bool(raw.get("doubleCorrupted", raw.get("double_corrupted", False))),
        flavour_text=flavour_text,
        granted_skills=granted_skills,
        properties=props,
        requirements=reqs,
        implicit_mods=implicit_mods_list,
        implicit_mod_details=implicit_mod_details,
        implicit_mod_range_hints=implicit_mod_range_hints,
        explicit_mods=explicit_mods_list,
        explicit_mod_details=explicit_mod_details,
        explicit_mod_range_hints=explicit_mod_range_hints,
        socketed_items=socketed_items,
        rune_mods=[strip_item_mod_text(str(m)) for m in raw.get("runeMods") or []],
        enchant_mods=[strip_item_mod_text(str(m)) for m in raw.get("enchantMods") or []],
        crafted_mods=[strip_item_mod_text(str(m)) for m in raw.get("craftedMods") or []],
        sockets=sockets,
        stack_size=raw.get("stackSize"),
        max_stack_size=raw.get("maxStackSize"),
        icon=raw.get("icon"),
        frame_type_id=frame_type_id_str,
        runeforged=runeforged,
        raw=None,
    )


_RUNEFORGED_NAME_RE = re.compile(r"^(Runemastered|Runeforged)\s", re.IGNORECASE)


def _is_runeforged_item(
    *,
    base_type: str,
    type_line: str,
    frame_type_id: str | None,
    frame_type: object,
) -> bool:
    if frame_type_id == "RunicUnique":
        return True
    if frame_type == 14:
        return True
    label = base_type or type_line
    return bool(_RUNEFORGED_NAME_RE.match(label.strip()))


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
