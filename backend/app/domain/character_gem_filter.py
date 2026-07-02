"""Filter character skill gems for display and Apprise (mirrors frontend gem filter)."""

from __future__ import annotations

import re

from app.domain.item import Item, strip_item_mod_text

_GEM_SLOTS = frozenset({"SkillSlots", "AscendancySkills", "DefaultAttackSkills"})
_TIERED_SUPPORT_RE = re.compile(r"\s+(I{1,3}|IV|V|VI{0,3}|IX|X)$")


def _property_text(item: Item) -> str:
    return " ".join(strip_item_mod_text(p.name) for p in item.properties).lower()


def is_lineage_support(item: Item) -> bool:
    return "lineage" in _property_text(item)


def is_generic_support(item: Item) -> bool:
    props = _property_text(item)
    if "lineage" in props:
        return False
    return "support" in props


def is_tiered_generic_support(item: Item) -> bool:
    return bool(_TIERED_SUPPORT_RE.search((item.type_line or "").strip()))


def is_notable_character_gem(item: Item) -> bool:
    """Show/queue active skills, ascendancy gems, and special supports — not socket fillers."""
    iid = item.inventory_id or ""
    if iid in ("AscendancySkills", "DefaultAttackSkills"):
        return True
    if is_lineage_support(item):
        return True
    if is_tiered_generic_support(item):
        return False
    if is_generic_support(item):
        return False
    return (item.rarity or "").lower() == "gem"


def should_include_character_item_in_apprise(item: Item) -> bool:
    """Exclude common tiered/generic supports from character Apprise backfill."""
    if (item.rarity or "").lower() == "gem":
        return is_notable_character_gem(item)
    iid = item.inventory_id or ""
    if iid in _GEM_SLOTS or is_generic_support(item) or is_lineage_support(item):
        return is_notable_character_gem(item)
    return True
