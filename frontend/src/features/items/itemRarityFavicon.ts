import type { Item, ItemRarity } from "@/api/types";

import { itemIconForCanvasProxy } from "@/utils/poecdnIcon";

const RARITY_FAVICON_PATH: Record<ItemRarity, string> = {
  Normal: "/icons/item-rarity/normal.svg",
  Magic: "/icons/item-rarity/magic.svg",
  Rare: "/icons/item-rarity/rare.svg",
  Unique: "/icons/item-rarity/unique.svg",
  Currency: "/icons/item-rarity/currency.svg",
  Gem: "/icons/item-rarity/gem.svg",
  DivinationCard: "/icons/item-rarity/divination.svg",
  QuestItem: "/icons/item-rarity/quest.svg",
};

/** Placeholder by PoE2 rarity (same-origin SVG) when the GGG icon URL is missing. */
export function itemRarityFaviconPath(rarity: ItemRarity): string {
  return RARITY_FAVICON_PATH[rarity] ?? RARITY_FAVICON_PATH.Normal;
}

/**
 * Official CDN art when `item.icon` is set, otherwise a rarity-tinted placeholder
 * (used everywhere item thumbnails appear).
 */
export function itemIconDisplayUrl(item: Pick<Item, "icon" | "rarity">): string {
  if (item.icon?.trim()) return item.icon;
  return itemRarityFaviconPath(item.rarity);
}

/** Same-origin path for html-to-image (avoids relative URL resolution quirks off-screen). */
function exportAbsoluteUrl(url: string): string {
  if (typeof window !== "undefined" && url.startsWith("/")) {
    return `${window.location.origin}${url}`;
  }
  return url;
}

/**
 * URL safe for `html-to-image` / same-origin: PoE CDN via proxy, else rarity SVG.
 */
export function itemIconForExportPng(item: Item): string {
  if (item.icon?.trim()) {
    const proxied = itemIconForCanvasProxy(item.icon) ?? item.icon;
    return exportAbsoluteUrl(proxied);
  }
  return exportAbsoluteUrl(itemRarityFaviconPath(item.rarity));
}
