"""Item → price-source key normalisation.

The matcher builds a stable key from an :class:`app.domain.item.Item` that a
price source can look up.  We intentionally keep it dumb: currency stacks
match by ``base_type`` alone, uniques by name, everything else by base+rarity
(+ stat window hash for rares which poe.ninja doesn't actually price but some
sources do).
"""

from __future__ import annotations

from pydantic import BaseModel

from app.domain.item import Item


class ItemKey(BaseModel):
    category: str  # "currency" | "unique" | "gem" | "rare" | "magic" | "normal" | "other"
    base_type: str
    name: str = ""
    rarity: str = "Normal"


def match_item(item: Item) -> ItemKey:
    rarity = item.rarity.lower()

    if rarity == "currency":
        return ItemKey(category="currency", base_type=item.type_line or item.base_type)
    if rarity == "unique":
        return ItemKey(
            category="unique",
            base_type=item.base_type,
            name=item.name,
            rarity="Unique",
        )
    if rarity == "gem":
        return ItemKey(category="gem", base_type=item.base_type or item.type_line)
    if rarity == "divinationcard":
        return ItemKey(category="card", base_type=item.type_line or item.base_type)
    if rarity == "rare":
        return ItemKey(category="rare", base_type=item.base_type, rarity="Rare")
    if rarity == "magic":
        return ItemKey(category="magic", base_type=item.base_type, rarity="Magic")
    return ItemKey(category=rarity or "normal", base_type=item.base_type)
