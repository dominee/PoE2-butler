"""Cumulative character stats from equipped :class:`Item` lists.

Mod lines (implicit, rune, explicit, …) are:

1. Cleaned and stripped of GGG display tags
2. Normalized to a *template* (every numeric literal replaced with ``#`` in order)
3. Summed *per template* across all items (and nested socketed items) — same shape → add numbers
4. Placed in a *section* via ordered keyword heuristics (see :func:`_classify_section`).

``#`` arity > 1 (e.g. *Adds 5 to 12 …*) is summed **element-wise** (total min, total max).
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import ClassVar, Literal

from pydantic import BaseModel, Field

from app.domain.item import Item, _strip_tags

# Numbers: optional sign, int or float (e.g. 8.2)
_NUM = re.compile(r"[-+]?\d+(?:\.\d+)?")
_TRAIL = re.compile(
    r"\s*[\(\[]?[^)\]]*(?:rune|soul|implicit|enchant|crafted|aug(mented)?)[\)\]]?\s*$",
    re.IGNORECASE,
)
_MULTISPACE = re.compile(r"\s+")

_OTHER = "other"

# Section order and human-readable titles (order defines UI sort).
_SECTION_META: ClassVar[tuple[tuple[str, str, int], ...]] = (
    ("conversion", "Conversion & extra damage", 0),
    ("resistances", "Resistances", 1),
    ("resources", "Life, mana, spirit & recovery", 2),
    ("attributes", "Attributes", 3),
    ("defences", "Armour, evasion, ES & mitigation", 4),
    ("critical", "Critical & accuracy", 5),
    ("speed", "Speeds", 6),
    ("ailments", "Ailments, curses & exposure", 7),
    ("charges", "Charges", 8),
    ("mana_sustain", "Reservation & cost", 9),
    ("damage", "Damage, penetration & hits", 10),
    (_OTHER, "Other", 11),
)
_SECTION_ORDER: ClassVar[dict[str, int]] = {m[0]: m[2] for m in _SECTION_META}
_SECTION_LABEL: ClassVar[dict[str, str]] = {m[0]: m[1] for m in _SECTION_META}

_CONVERSION_PAT: ClassVar[str] = (
    r"as extra|"
    r"elemental damage converted|damage converted|"
    r"gain [^.]{0,200}as extra|"
    r"of [^.]{0,120}as extra|"
    r"as (?:chaos|physical|lightning|cold|fire|elemental) damage$"
)


def _classify_section(t: str) -> str:
    """Return section id. Order is specific → general (e.g. conversion before damage)."""
    t = t.lower()
    if re.search(_CONVERSION_PAT, t):
        return "conversion"
    if re.search(r"resistance| to all element|all elemental|elemental res", t):
        return "resistances"
    if re.search(
        r"maximum life|maximum mana| to spirit|spirit |regeneration|regenerat|"
        r"leech|recoup|gained (?:on|per)|per (?:level|second|socket|socket filled)|"
        r"life gained|taken from mana|taken from life|taken as|"
        r"of damage is taken from|taken as damage",
        t,
    ):
        return "resources"
    if re.search(
        r"\+?[-]?\d+(?:\.\d+)?%?\s*to (?:strength|dexterity|intelligence|str|dex|int)\b|"
        r"\+?[-]?\d+(?:\.\d+)?%?\s*to (?:strength|dexterity|intelligence)(?:$|[,.\s])|"
        r"to (?:strength|dexterity|intelligence)(?:$| from)",
        t,
    ):
        return "attributes"
    if re.search(
        r"armou?r|evasion( rating)?|energy shield|increased defences?|increased armour, evasion|"
        r"spell suppress|suppression|dodge|block|chance to block|increased maximum energy shield|"
        r"ward|deflect",
        t,
    ):
        return "defences"
    if re.search(r"critical|accuracy|multiplier|lucky", t):
        return "critical"
    if re.search(r"attack speed|cast speed|movement speed|haste|action speed", t):
        return "speed"
    if re.search(
        r"ailment|magnitude|non-damaging ailment|chill|freeze|shock|"
        r"scorch|brittle|sap\b|curses?|exposure|"
        r"ignite|bleed|poison",
        t,
    ):
        return "ailments"
    if re.search(r"charge|frenzy|endurance|power", t):
        return "charges"
    if re.search(r"reservation|mana cost|cost of|skill cost|reduced cost|increased mana", t):
        return "mana_sustain"
    if re.search(
        r"penetrat|adds |damage to|with weapons?|warcry|spell damage|melee damage|area damage|"
        r"projectile|chaining|chain(?!s)|\bdps\b|"
        r"hits? against|weapon range|increased physical|increased spell|"
        r"increased elemental|increased chaos|increased lightning|increased fire|increased cold|"
        r"increased damage|more damage|less damage|dealt|attack\b",
        t,
    ) or re.search(
        r"physical damage|elemental damage|chaos damage|lightning damage|fire damage|"
        r"cold damage|damage over time|damage taken",
        t,
    ):
        return "damage"
    return _OTHER


def _order_index(section_id: str) -> int:
    return _SECTION_ORDER.get(section_id, 50)


@dataclass
class _AccRow:
    template: str
    values: list[float] = field(default_factory=list)
    label: str = ""


@dataclass
class _Acc:
    rows: dict[str, _AccRow] = field(default_factory=dict)

    def add(self, template: str, nums: list[float], display_label: str) -> None:
        if not nums:
            return
        if template not in self.rows:
            self.rows[template] = _AccRow(
                template=template,
                values=[0.0] * len(nums),
                label=display_label,
            )
        row = self.rows[template]
        for i, n in enumerate(nums):
            row.values[i] += n
        if not row.label and display_label:
            row.label = display_label

    def to_list(self) -> list[_AccRow]:
        return list(self.rows.values())


def _clean_mod_line(s: str) -> str:
    t = _TRAIL.sub("", s.strip())
    return _MULTISPACE.sub(" ", t)


def _template_from_line(s: str) -> tuple[str, list[float]] | None:
    """Build template with # placeholders; collect numeric values in order."""
    t = s.strip()
    if not t:
        return None
    values: list[float] = []
    out: list[str] = []
    pos = 0
    for m in _NUM.finditer(t):
        out.append(t[pos : m.start()])
        v = float(m.group(0))
        values.append(v)
        out.append("#")
        pos = m.end()
    out.append(t[pos:])
    if not values:
        return None
    template = _MULTISPACE.sub(" ", "".join(out)).strip()
    return template, values


class StatRow(BaseModel):
    key: str
    label: str
    values: list[float] = Field(default_factory=list)
    value_shape: Literal["auto"] = "auto"


class StatSection(BaseModel):
    id: str
    label: str
    sort_index: int = 0
    rows: list[StatRow] = Field(default_factory=list)


class EquipmentStatSummary(BaseModel):
    sections: list[StatSection] = Field(default_factory=list)


def _all_mod_texts(item: Item) -> list[str]:
    parts: list[str] = []
    for group in (
        item.implicit_mods,
        item.rune_mods,
        item.explicit_mods,
        item.crafted_mods,
        item.enchant_mods,
    ):
        parts.extend(group)
    for s in item.socketed_items:
        parts.extend(_all_mod_texts(s))
    return [_strip_tags(m) for m in parts if m]


def _row_sort_key(r: StatRow) -> str:
    return (r.label or r.key).lower()


def summarize_equipment(items: list[Item]) -> EquipmentStatSummary:
    per_section: dict[str, _Acc] = defaultdict(_Acc)
    for it in items:
        for raw in _all_mod_texts(it):
            clean = _clean_mod_line(raw)
            parsed = _template_from_line(clean)
            if not parsed:
                continue
            template, nums = parsed
            sid = _classify_section(clean)
            per_section[sid].add(template, nums, clean)
    out_sections: list[StatSection] = []
    for sid, default_label, _ in _SECTION_META:
        if sid not in per_section or not per_section[sid].rows:
            continue
        acc = per_section[sid]
        rows: list[StatRow] = []
        for r in acc.to_list():
            rows.append(
                StatRow(
                    key=r.template,
                    label=r.label or r.template,
                    values=r.values,
                )
            )
        rows.sort(key=_row_sort_key)
        out_sections.append(
            StatSection(
                id=sid,
                label=_SECTION_LABEL.get(sid, default_label),
                sort_index=_order_index(sid),
                rows=rows,
            )
        )
    return EquipmentStatSummary(sections=out_sections)
