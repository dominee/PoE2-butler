import type { Item, ItemRarity, PriceEstimate } from "@/api/types";

import { useIsItemPriceInflight } from "@/features/pricing/PriceInflightContext";
import { PriceBadge } from "./PriceBadge";
import { itemIconDisplayUrl } from "./itemRarityFavicon";
import { ModText } from "./ItemModPresentation";
import { isRuneforgedItem, runeforgedBorderClass } from "./itemVisualStyles";

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

export type ActivityStatus = "new" | "changed" | undefined;

export interface ItemCardProps {
  item: Item;
  selected?: boolean;
  onClick?: (item: Item) => void;
  compact?: boolean;
  price?: PriceEstimate | null;
  valuableThreshold?: number;
  activityStatus?: ActivityStatus;
  className?: string;
}

const ACTIVITY_DOT: Record<NonNullable<ActivityStatus>, string> = {
  new: "bg-emerald-400",
  changed: "bg-amber-400",
};

export function ItemCard({
  item,
  selected,
  onClick,
  compact,
  price,
  valuableThreshold,
  activityStatus,
  className,
}: ItemCardProps) {
  const runeforged = isRuneforgedItem(item);
  const priceInflight = useIsItemPriceInflight(item.id);
  const rarityClass = runeforged
    ? runeforgedBorderClass
    : (RARITY_CLASSNAME[item.rarity] ?? RARITY_CLASSNAME.Normal);
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
        "panel relative w-full text-left border",
        "min-h-[72px] px-3 py-2 transition focus:outline-none focus-visible:ring-2 focus-visible:ring-ember-400/70",
        "hover:border-ember-400/80",
        selected ? "ring-2 ring-ember-400" : "",
        rarityClass,
        className ?? "",
      ]
        .filter(Boolean)
        .join(" ")}
      aria-label={`Item ${item.name || item.type_line}`}
      data-testid="item-card"
    >
      {/* Activity status dot */}
      {activityStatus && (
        <span
          className={`absolute right-1.5 top-1.5 h-2 w-2 rounded-full ${ACTIVITY_DOT[activityStatus]}`}
          title={activityStatus === "new" ? "New item" : "Changed item"}
        />
      )}
      {priceInflight && (
        <span
          className="absolute left-1.5 top-1.5 rounded border border-amber-500/40 bg-amber-500/15 px-1 py-0.5 text-[9px] font-medium uppercase tracking-wide text-amber-200/95"
          title="Hybrid price estimate queued or running"
        >
          Updating
        </span>
      )}
      <div className="flex items-start justify-between gap-2">
        {/* Icon thumbnail */}
        {!compact && (
          <img
            src={itemIconDisplayUrl(item)}
            alt=""
            className="mt-0.5 h-8 w-8 shrink-0 object-contain"
            loading="lazy"
            onError={(e) => { (e.currentTarget as HTMLImageElement).style.display = "none"; }}
          />
        )}
        <div className="min-w-0 flex-1">
          {item.name && (
            <div className={`font-display text-sm leading-tight ${nameClass}`}>
              {item.name}
            </div>
          )}
          <div className="break-words text-xs text-parchment-100/80">{item.type_line}</div>
        </div>
        <div className="flex shrink-0 flex-col items-end gap-0.5 text-[10px] uppercase tracking-wide text-ui-muted">
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
          {item.explicit_mods.map((mod, idx) => (
            <li key={`${item.id}-mod-${idx}`} className="break-words leading-snug">
              <ModText raw={mod} />
            </li>
          ))}
        </ul>
      )}
    </button>
  );
}
