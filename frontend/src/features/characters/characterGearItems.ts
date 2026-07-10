import type { CharacterDetail, Item, PriceEstimate } from "@/api/types";
import {
  type CurrencyChaosPair,
  getChaosEquivDisplayParts,
} from "@/features/items/itemMetrics";
import { filterCharacterGemsForPricing } from "@/features/characters/characterGemFilter";
import { collectPaperDollItems } from "@/features/characters/paperDollItems";

/** Paper-doll slots + Lineage support gems + jewels (gear estimate denominator). */
export function collectCharacterGearPricingItems(
  detail: Pick<CharacterDetail, "equipped" | "gems" | "jewels" | "inventory">,
): Item[] {
  const seen = new Set<string>();
  const out: Item[] = [];
  for (const item of [
    ...collectPaperDollItems(detail),
    ...filterCharacterGemsForPricing(detail.gems ?? []),
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

/** e.g. ``100div (3600ex) [4/25 items]`` */
export function formatGearEstimateLabel(
  estimate: GearEstimate,
  rates: CurrencyChaosPair | null | undefined,
): string {
  const countSuffix =
    estimate.totalCount > 0
      ? ` [${estimate.pricedCount}/${estimate.totalCount} items]`
      : "";
  if (estimate.totalChaos <= 0) {
    return estimate.totalCount > 0 ? `—${countSuffix}` : "—";
  }
  const parts = getChaosEquivDisplayParts(estimate.totalChaos, rates);
  if (parts.kind === "chaos") {
    return `${parts.text}${countSuffix}`;
  }
  return `${parts.divAmount}div (${parts.exAmount}ex)${countSuffix}`;
}
