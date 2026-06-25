import type { Item, ItemRarity } from "@/api/types";

/** Runemastered / Runeforged league items (light blue in-game outline). */
export const RUNEFORGED_BORDER_RGBA = "rgba(110, 196, 232, 0.72)";
export const runeforgedBorderClass =
  "text-parchment-50 border-[#6ec4e8]/75 shadow-[0_0_10px_rgba(110,196,232,0.25)]";

const RUNEFORGED_NAME_RE = /^(Runemastered|Runeforged)\s/i;

export function isRuneforgedItem(item: Item): boolean {
  if (item.runeforged) return true;
  if (item.frame_type_id === "RunicUnique") return true;
  const label = item.base_type || item.type_line;
  return RUNEFORGED_NAME_RE.test(label);
}

/** Inline border colour for the detail pane (overrides the panel base). */
export const PANE_RARITY_BORDER: Partial<Record<ItemRarity, string>> = {
  Magic: "rgba(136,136,255,0.45)",
  Rare: "rgba(255,255,119,0.35)",
  Unique: "rgba(175,96,37,0.9)",
  Currency: "rgba(170,158,130,0.5)",
  Gem: "rgba(27,162,155,0.55)",
  DivinationCard: "rgba(100,100,100,0.4)",
};

export function paneBorderColor(item: Item): string {
  if (isRuneforgedItem(item)) return RUNEFORGED_BORDER_RGBA;
  return PANE_RARITY_BORDER[item.rarity as ItemRarity] ?? "rgba(80,80,90,0.45)";
}

/** Tailwind text class for the item name in the header. */
export const RARITY_NAME_CLASS: Partial<Record<ItemRarity, string>> = {
  Magic: "text-rarity-magic",
  Rare: "text-rarity-rare",
  Unique: "text-rarity-unique",
  Gem: "text-rarity-gem",
  Currency: "text-rarity-currency",
};
