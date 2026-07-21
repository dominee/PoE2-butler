import type { CharacterDetail, Item } from "@/api/types";

/** Equipment slots rendered on the paper doll (matches backend ``_EQUIPPED_SLOTS`` minus flask/charm). */
export const PAPER_DOLL_SLOT_IDS = new Set([
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
]);

/**
 * Collect gear for the paper doll from every character detail bucket.
 * Prefer the first item per slot (equipped wins over inventory when listed first).
 */
export function collectPaperDollItems(
  detail: Pick<CharacterDetail, "equipped" | "gems" | "jewels" | "inventory">,
): Item[] {
  const bySlot = new Map<string, Item>();
  for (const item of [...detail.equipped, ...(detail.inventory ?? [])]) {
    const slot = item.inventory_id;
    if (slot && PAPER_DOLL_SLOT_IDS.has(slot) && !bySlot.has(slot)) {
      bySlot.set(slot, item);
    }
  }
  return [...bySlot.values()];
}

/**
 * Collect charm items from equipped (inventory_id === "Charm" or is_charm === true).
 * Sorted by x-position so they appear in flask-bar order.
 */
export function collectCharmItems(
  detail: Pick<CharacterDetail, "equipped" | "inventory">,
): Item[] {
  const charms = [
    ...(detail.equipped ?? []),
    ...(detail.inventory ?? []),
  ].filter((item) => item.inventory_id === "Charm" || item.is_charm);
  // Sort by x so charms appear left-to-right in their flask bar position.
  return charms.slice().sort((a, b) => (a.x ?? 0) - (b.x ?? 0));
}
