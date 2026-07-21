import type { CharacterDetail, Item, PriceEstimate } from "@/api/types";
import {
  type CurrencyChaosPair,
  getChaosEquivDisplayParts,
} from "@/features/items/itemMetrics";
import {
  filterCharacterGemsForPricing,
  walkCharacterGemCandidates,
} from "@/features/characters/characterGemFilter";
import { collectPaperDollItems } from "@/features/characters/paperDollItems";

/** Return true when an item is a charm (unique or normal). */
export function isCharmItem(item: Item): boolean {
  return item.inventory_id === "Charm" || item.is_charm === true;
}

/** Return true when a charm should be included in pricing (unique charms only). */
export function isUniqueCharm(item: Item): boolean {
  return isCharmItem(item) && item.rarity === "Unique";
}

/**
 * Paper-doll slots + Lineage support gems (including those nested in skill socketed_items) +
 * jewels + unique charms.
 * Normal charms are intentionally excluded from price checks.
 */
export function collectCharacterGearPricingItems(
  detail: Pick<CharacterDetail, "equipped" | "gems" | "jewels" | "inventory">,
): Item[] {
  const seen = new Set<string>();
  const out: Item[] = [];
  const uniqueCharms = (detail.equipped ?? []).filter(isUniqueCharm);
  for (const item of [
    ...collectPaperDollItems(detail),
    ...filterCharacterGemsForPricing([...walkCharacterGemCandidates(detail)]),
    ...(detail.jewels ?? []),
    ...uniqueCharms,
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
