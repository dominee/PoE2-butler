import type { ItemProperty } from "@/api/types";

/** Drop category-header properties (those with empty values, e.g. "Amulet"). */
export function usefulProperties(props: ItemProperty[]): ItemProperty[] {
  return props.filter((p) => p.value != null && p.value !== "");
}

/**
 * PoE2 mod ordering: prefixes come first (≤3), suffixes follow (≤3).
 * We split at position 3 for Rare, at 1 for Magic.
 */
export function splitExplicitMods(
  mods: string[],
  rarity: string,
): { prefixes: string[]; suffixes: string[] } {
  if (mods.length === 0) return { prefixes: [], suffixes: [] };
  if (rarity === "Rare") {
    const cut = Math.min(3, mods.length);
    return { prefixes: mods.slice(0, cut), suffixes: mods.slice(cut) };
  }
  if (rarity === "Magic" && mods.length >= 2) {
    return { prefixes: [mods[0]], suffixes: mods.slice(1) };
  }
  return { prefixes: mods, suffixes: [] };
}
