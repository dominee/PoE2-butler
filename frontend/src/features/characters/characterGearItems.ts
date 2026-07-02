import type { CharacterDetail, Item, PriceEstimate } from "@/api/types";
import { filterNotableCharacterGems } from "@/features/characters/characterGemFilter";
import { collectPaperDollItems } from "@/features/characters/paperDollItems";

/** Paper-doll slots + notable skill gems + jewels (gear estimate denominator). */
export function collectCharacterGearPricingItems(
  detail: Pick<CharacterDetail, "equipped" | "gems" | "jewels" | "inventory">,
): Item[] {
  const seen = new Set<string>();
  const out: Item[] = [];
  for (const item of [
    ...collectPaperDollItems(detail),
    ...filterNotableCharacterGems(detail.gems ?? []),
    ...(detail.jewels ?? []),
  ]) {
    if (!seen.has(item.id)) {
      seen.add(item.id);
      out.push(item);
    }
  }
  return out;
}

export interface GearEstimate {
  totalChaos: number;
  pricedCount: number;
  totalCount: number;
}

export function computeGearEstimate(
  items: Item[],
  prices: Record<string, PriceEstimate | null | undefined> | undefined,
): GearEstimate {
  let totalChaos = 0;
  let pricedCount = 0;
  for (const item of items) {
    const price = prices?.[item.id];
    if (price?.chaos_equiv != null) {
      totalChaos += price.chaos_equiv;
      pricedCount += 1;
    }
  }
  return { totalChaos, pricedCount, totalCount: items.length };
}
