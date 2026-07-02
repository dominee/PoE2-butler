"""Item → price-source key normalisation.

The matcher builds a stable key from an :class:`app.domain.item.Item` that a
price source can look up.  We intentionally keep it dumb: currency stacks
match by ``base_type`` alone, uniques by name, everything else by base+rarity
(+ stat window hash for rares which poe.ninja doesn't actually price but some
sources do).
"""

from __future__ import annotations

from pydantic import BaseModel

from app.domain.item import Item, strip_item_mod_text


class ItemKey(BaseModel):
    category: str  # currency | unique | lineage_gem | skill_gem | gem_trade | ...
    base_type: str
    name: str = ""
    rarity: str = "Normal"
    gem_level: int | None = None


def _property_text(item: Item) -> str:
    return " ".join(strip_item_mod_text(p.name) for p in item.properties).lower()


def _gem_level_from_item(item: Item) -> int | None:
    for prop in item.properties:
        if strip_item_mod_text(prop.name).lower() != "level":
            continue
        raw = (prop.value or "").strip()
        if raw.isdigit():
            return int(raw)
    return None


def _is_lineage_gem(item: Item) -> bool:
    return "lineage" in _property_text(item)


def _is_charm_base(base_type: str) -> bool:
    return base_type.lower().endswith(" charm")


def _is_flask_base(base_type: str) -> bool:
    return " flask" in base_type.lower()


def match_item(item: Item) -> ItemKey:
    rarity = item.rarity.lower()

    if rarity == "currency":
        return ItemKey(category="currency", base_type=item.type_line or item.base_type)
    if rarity == "unique":
        base = item.base_type or item.type_line
        display = (item.name or item.type_line or base).strip()
        if _is_charm_base(base):
            return ItemKey(
                category="unique_charm",
                base_type=base,
                name=display,
                rarity="Unique",
            )
        if _is_flask_base(base):
            return ItemKey(
                category="unique_flask",
                base_type=base,
                name=display,
                rarity="Unique",
            )
        return ItemKey(
            category="unique",
            base_type=base,
            name=item.name,
            rarity="Unique",
        )
    if rarity == "gem":
        display = (item.type_line or item.base_type).strip()
        if item.corrupted:
            return ItemKey(
                category="gem_trade",
                base_type=item.base_type or item.type_line,
                name=display,
                gem_level=_gem_level_from_item(item),
            )
        if _is_lineage_gem(item):
            return ItemKey(
                category="lineage_gem",
                base_type=item.base_type or item.type_line,
                name=display,
            )
        return ItemKey(
            category="skill_gem",
            base_type=item.base_type or item.type_line,
            name=display,
            gem_level=_gem_level_from_item(item),
        )
    if rarity == "divinationcard":
        return ItemKey(category="card", base_type=item.type_line or item.base_type)
    if rarity == "rare":
        return ItemKey(category="rare", base_type=item.base_type, rarity="Rare")
    if rarity == "magic":
        return ItemKey(category="magic", base_type=item.base_type, rarity="Magic")
    return ItemKey(category=rarity or "normal", base_type=item.base_type)
