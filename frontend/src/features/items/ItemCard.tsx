import type { Item, ItemRarity, PriceEstimate } from "@/api/types";
import { stripTags } from "@/utils/modText";

import { PriceBadge } from "./PriceBadge";

const RARITY_CLASSNAME: Record<ItemRarity, string> = {
  Normal: "text-rarity-normal border-ink-600",
  Magic: "text-rarity-magic border-rarity-magic/40",
  Rare: "text-rarity-rare border-rarity-rare/40",
  Unique: "text-rarity-unique border-rarity-unique/40",
  Currency: "text-rarity-currency border-rarity-currency/40",
  Gem: "text-rarity-gem border-rarity-gem/40",
  DivinationCard: "text-parchment-50 border-ink-600",
  QuestItem: "text-rarity-quest border-rarity-quest/40",
};

/** Rarity color applied to the item name text (follows in-game tooltip style). */
const RARITY_NAME_CLASS: Partial<Record<ItemRarity, string>> = {
  Magic: "text-rarity-magic",
  Rare: "text-rarity-rare",
  Unique: "text-rarity-unique",
  Gem: "text-rarity-gem",
  Currency: "text-rarity-currency",
};

export interface ItemCardProps {
  item: Item;
  selected?: boolean;
  onClick?: (item: Item) => void;
  compact?: boolean;
  price?: PriceEstimate | null;
  valuableThreshold?: number;
}

export function ItemCard({
  item,
  selected,
  onClick,
  compact,
  price,
  valuableThreshold,
}: ItemCardProps) {
  const rarityClass = RARITY_CLASSNAME[item.rarity] ?? RARITY_CLASSNAME.Normal;
  const nameClass = RARITY_NAME_CLASS[item.rarity] ?? "text-parchment-50";
  const stack =
    item.stack_size != null && item.max_stack_size != null
      ? `${item.stack_size}/${item.max_stack_size}`
      : null;

  return (
    <button
      type="button"
      onClick={onClick ? () => onClick(item) : undefined}
      className={[
        "panel w-full text-left border",
        "min-h-[72px] px-3 py-2 transition focus:outline-none",
        "hover:border-ember-400/80",
        selected ? "ring-2 ring-ember-400" : "",
        rarityClass,
      ]
        .filter(Boolean)
        .join(" ")}
      aria-label={`Item ${item.name || item.type_line}`}
      data-testid="item-card"
    >
      <div className="flex items-baseline justify-between gap-2">
        <div className="min-w-0">
          {item.name && (
            <div className={`font-display text-sm leading-tight ${nameClass}`}>
              {item.name}
            </div>
          )}
          <div className="break-words text-xs text-parchment-100/80">{item.type_line}</div>
        </div>
        <div className="flex shrink-0 flex-col items-end gap-0.5 text-[10px] uppercase tracking-wide text-ink-500">
          {price !== undefined && (
            <PriceBadge price={price ?? null} threshold={valuableThreshold} compact />
          )}
          {item.ilvl != null && <span>ilvl {item.ilvl}</span>}
          {stack && <span>{stack}</span>}
          {item.corrupted && <span className="text-red-400">corrupted</span>}
        </div>
      </div>
      {!compact && item.explicit_mods.length > 0 && (
        <ul className="mt-1 list-none text-[11px] text-rarity-magic/90">
          {item.explicit_mods.slice(0, 4).map((mod, idx) => (
            <li key={`${item.id}-mod-${idx}`} className="break-words leading-snug">
              {stripTags(mod)}
            </li>
          ))}
          {item.explicit_mods.length > 4 && (
            <li className="text-ink-500">+{item.explicit_mods.length - 4} more</li>
          )}
        </ul>
      )}
    </button>
  );
}
