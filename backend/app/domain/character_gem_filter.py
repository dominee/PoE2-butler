"""Filter character skill gems for display and Apprise (mirrors frontend gem filter)."""

from __future__ import annotations

import re

from app.domain.item import Item, strip_item_mod_text

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


def is_character_skill_gem(item: Item) -> bool:
    """Active skill gems (including ascendancy and item-granted), not supports."""
    iid = item.inventory_id or ""
    if iid in ("AscendancySkills", "DefaultAttackSkills"):
        return True
    if is_lineage_support(item):
        return False
    if is_tiered_generic_support(item):
        return False
    if is_generic_support(item):
        return False
    return (item.rarity or "").lower() == "gem"


def is_displayed_in_skill_gems_section(item: Item) -> bool:
    """Skill gems section: active skills plus Lineage supports."""
    return is_character_skill_gem(item) or is_lineage_support(item)


def should_include_character_gem_in_pricing(item: Item) -> bool:
    """Only Lineage supports count toward character gear total and Apprise."""
    return is_lineage_support(item)


def is_notable_character_gem(item: Item) -> bool:
    """Prefer is_displayed_in_skill_gems_section."""
    return is_displayed_in_skill_gems_section(item)


def should_include_character_item_in_apprise(item: Item) -> bool:
    """Exclude skill gems and generic supports; only Lineage gems are priced."""
    if (item.rarity or "").lower() == "gem":
        return is_lineage_support(item)
    return True
