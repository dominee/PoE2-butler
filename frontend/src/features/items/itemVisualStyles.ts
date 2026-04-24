import type { ItemRarity } from "@/api/types";

/** Inline border colour for the detail pane (overrides the panel base). */
export const PANE_RARITY_BORDER: Partial<Record<ItemRarity, string>> = {
  Magic: "rgba(136,136,255,0.45)",
  Rare: "rgba(255,255,119,0.35)",
  Unique: "rgba(175,96,37,0.9)",
  Currency: "rgba(170,158,130,0.5)",
  Gem: "rgba(27,162,155,0.55)",
  DivinationCard: "rgba(100,100,100,0.4)",
};

/** Tailwind text class for the item name in the header. */
export const RARITY_NAME_CLASS: Partial<Record<ItemRarity, string>> = {
  Magic: "text-rarity-magic",
  Rare: "text-rarity-rare",
  Unique: "text-rarity-unique",
  Gem: "text-rarity-gem",
  Currency: "text-rarity-currency",
};
