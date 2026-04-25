/**
 * Large-icon grid layout for stash browsing.
 *
 * Displays items as their base item icons in a responsive grid with a stat
 * summary overlay on hover.  Items without icons fall back to a coloured text
 * tile.  Rarity, activity status, and valuable-item signals are all preserved.
 */

import type { Item, ItemRarity, PriceEstimate } from "@/api/types";
import { formatChaos } from "@/features/items/itemMetrics";
import { stripTags } from "@/utils/modText";

const RARITY_BORDER: Record<ItemRarity, string> = {
  Normal: "border-ink-500",
  Magic: "border-rarity-magic/60",
  Rare: "border-rarity-rare/60",
  Unique: "border-rarity-unique/60",
  Currency: "border-rarity-currency/60",
  Gem: "border-rarity-gem/60",
  DivinationCard: "border-parchment-100/40",
  QuestItem: "border-rarity-quest/60",
};

const RARITY_BG: Record<ItemRarity, string> = {
  Normal: "bg-ink-800",
  Magic: "bg-ink-800",
  Rare: "bg-ink-900",
  Unique: "bg-ink-900",
  Currency: "bg-ink-900",
  Gem: "bg-ink-900",
  DivinationCard: "bg-ink-800",
  QuestItem: "bg-ink-900",
};

export interface StashIconGridProps {
  items: Item[];
  selectedItemId: string | null;
  onSelect: (item: Item) => void;
  highlightIds?: Set<string>;
  prices?: Record<string, PriceEstimate | null>;
  valuableThreshold?: number;
  activityMap?: Map<string, "new" | "changed">;
}

export function StashIconGrid({
  items,
  selectedItemId,
  onSelect,
  highlightIds,
  prices,
  valuableThreshold,
  activityMap,
}: StashIconGridProps) {
  if (items.length === 0) {
    return <p className="text-sm text-ink-500">No items in this tab.</p>;
  }

  return (
    <div
      className="grid gap-1"
      style={{ gridTemplateColumns: "repeat(auto-fill, minmax(64px, 1fr))" }}
      role="grid"
      aria-label="Stash icon grid"
    >
      {items.map((item) => {
        const borderClass = RARITY_BORDER[item.rarity] ?? RARITY_BORDER.Normal;
        const bgClass = RARITY_BG[item.rarity] ?? RARITY_BG.Normal;
        const selected = item.id === selectedItemId;
        const highlighted = highlightIds?.has(item.id);
        const price = prices?.[item.id];
        const valuable =
          price && valuableThreshold != null && price.chaos_equiv >= valuableThreshold;
        const activityStatus = activityMap?.get(item.id);

        return (
          <button
            type="button"
            key={item.id}
            onClick={() => onSelect(item)}
            className={[
              "group relative aspect-square overflow-hidden rounded border transition",
              "focus:outline-none focus-visible:ring-2 focus-visible:ring-ember-400",
              "hover:z-10 hover:ring-2 hover:ring-ember-400",
              bgClass,
              borderClass,
              selected ? "ring-2 ring-ember-400" : "",
              highlighted ? "outline outline-2 outline-yellow-400" : "",
            ]
              .filter(Boolean)
              .join(" ")}
            aria-label={item.name || item.type_line}
            data-testid="stash-icon-cell"
          >
            {/* Activity dot */}
            {activityStatus && (
              <span
                className={[
                  "absolute right-0.5 top-0.5 z-10 h-1.5 w-1.5 rounded-full",
                  activityStatus === "new" ? "bg-emerald-400" : "bg-amber-400",
                ].join(" ")}
                aria-label={activityStatus === "new" ? "New" : "Changed"}
              />
            )}

            {/* Icon */}
            {item.icon ? (
              <img
                src={item.icon}
                alt={item.name || item.type_line}
                className="h-full w-full object-contain p-1"
                loading="lazy"
              />
            ) : (
              <span className="flex h-full w-full items-center justify-center p-0.5 text-center text-[10px] leading-tight text-parchment-100/80">
                {item.name || item.type_line}
              </span>
            )}

            {/* Stack size */}
            {item.stack_size != null && item.stack_size > 1 && (
              <span className="absolute bottom-0.5 right-0.5 rounded bg-ink-950/80 px-0.5 text-[9px] font-medium text-parchment-100/90">
                {item.stack_size}
              </span>
            )}

            {/* Price badge */}
            {price && (
              <span
                className={[
                  "absolute bottom-0.5 left-0.5 rounded px-0.5 text-[9px] font-medium",
                  valuable
                    ? "bg-yellow-900/90 text-yellow-300"
                    : "bg-ink-950/80 text-parchment-100/70",
                ].join(" ")}
              >
                {formatChaos(price.chaos_equiv)}c
              </span>
            )}

            {/* Hover tooltip overlay */}
            <div className="pointer-events-none absolute inset-x-0 bottom-0 z-30 flex flex-col gap-0.5 bg-ink-950/95 p-1 opacity-0 transition-opacity group-hover:opacity-100">
              <span className="line-clamp-2 text-[9px] font-semibold leading-tight text-parchment-50">
                {item.name || item.type_line}
              </span>
              {item.name && (
                <span className="line-clamp-1 text-[8px] text-parchment-100/60">
                  {item.type_line}
                </span>
              )}
              {item.ilvl != null && (
                <span className="text-[8px] text-ink-400">iLvl {item.ilvl}</span>
              )}
              {item.explicit_mods.slice(0, 3).map((mod, i) => (
                <span key={i} className="line-clamp-1 text-[8px] text-rarity-magic/80">
                  {stripTags(mod)}
                </span>
              ))}
            </div>
          </button>
        );
      })}
    </div>
  );
}
