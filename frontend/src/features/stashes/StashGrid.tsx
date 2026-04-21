import type { Item, ItemRarity, PriceEstimate } from "@/api/types";
import { formatChaos } from "@/features/items/PriceBadge";
import { stripTags } from "@/utils/modText";

const RARITY_BG: Record<ItemRarity, string> = {
  Normal: "bg-ink-700 border-ink-500 text-rarity-normal",
  Magic: "bg-ink-800 border-rarity-magic/60 text-rarity-magic",
  Rare: "bg-ink-800 border-rarity-rare/60 text-rarity-rare",
  Unique: "bg-ink-800 border-rarity-unique/60 text-rarity-unique",
  Currency: "bg-ink-800 border-rarity-currency/60 text-rarity-currency",
  Gem: "bg-ink-800 border-rarity-gem/60 text-rarity-gem",
  DivinationCard: "bg-ink-800 border-parchment-100/50 text-parchment-50",
  QuestItem: "bg-ink-800 border-rarity-quest/60 text-rarity-quest",
};

export interface StashGridProps {
  tabType: string;
  items: Item[];
  selectedItemId: string | null;
  onSelect: (item: Item) => void;
  highlightIds?: Set<string>;
  prices?: Record<string, PriceEstimate | null>;
  valuableThreshold?: number;
  activityMap?: Map<string, "new" | "changed">;
}

const CELL = 34;
const GRID_W = 12;
const GRID_H = 12;

export function StashGrid({
  tabType,
  items,
  selectedItemId,
  onSelect,
  highlightIds,
  prices,
  valuableThreshold,
  activityMap,
}: StashGridProps) {
  const width = tabType === "QuadStash" ? GRID_W * 2 : GRID_W;
  const height = tabType === "QuadStash" ? GRID_H * 2 : GRID_H;

  return (
    <div
      className="relative border border-ink-700 bg-ink-950/70"
      style={{ width: width * CELL, height: height * CELL }}
      role="grid"
      aria-label={`Stash grid (${width} x ${height})`}
    >
      {renderBackdrop(width, height)}
      {items.map((item) => {
        if (item.x == null || item.y == null) return null;
        const rarityClass = RARITY_BG[item.rarity] ?? RARITY_BG.Normal;
        const selected = item.id === selectedItemId;
        const highlighted = highlightIds?.has(item.id);
        const price = prices?.[item.id];
        const valuable =
          price && valuableThreshold != null && price.chaos_equiv >= valuableThreshold;
        const activityStatus = activityMap?.get(item.id);
        const cellW = item.w * CELL;
        const cellH = item.h * CELL;

        return (
          <button
            type="button"
            key={item.id}
            onClick={() => onSelect(item)}
            className={[
              "group absolute overflow-hidden border text-[10px] transition",
              "focus:outline-none focus-visible:ring-2 focus-visible:ring-ember-400",
              "hover:z-20 hover:ring-2 hover:ring-ember-400",
              selected ? "z-10 ring-2 ring-ember-400" : "",
              highlighted ? "outline outline-2 outline-yellow-400" : "",
              rarityClass,
            ]
              .filter(Boolean)
              .join(" ")}
            style={{
              left: item.x * CELL,
              top: item.y * CELL,
              width: cellW,
              height: cellH,
            }}
            aria-label={`${item.name || item.type_line} at ${item.x},${item.y}`}
            title={`${item.name || ""}\n${item.type_line}`.trim()}
            data-testid="stash-cell"
          >
            {/* Activity status dot */}
            {activityStatus && (
              <span
                className={[
                  "absolute right-0.5 top-0.5 z-10 h-1.5 w-1.5 rounded-full",
                  activityStatus === "new" ? "bg-emerald-400" : "bg-amber-400",
                ].join(" ")}
                aria-label={activityStatus === "new" ? "New item" : "Changed item"}
              />
            )}

            {/* Item icon — primary content */}
            {item.icon ? (
              <>
                <img
                  src={item.icon}
                  alt=""
                  className="h-full w-full object-contain"
                  loading="lazy"
                  onError={(e) => {
                    (e.currentTarget as HTMLImageElement).style.display = "none";
                    if (e.currentTarget.nextElementSibling) {
                      (e.currentTarget.nextElementSibling as HTMLElement).style.display = "flex";
                    }
                  }}
                />
                {/* Fallback text (hidden while image loads) */}
                <div
                  className="hidden h-full w-full flex-col items-center justify-center gap-0.5 px-0.5 text-center leading-tight"
                  aria-hidden="true"
                >
                  <span className="line-clamp-2">{item.name || item.type_line}</span>
                </div>
              </>
            ) : (
              /* No icon — text fallback */
              <div className="flex h-full w-full flex-col items-center justify-center gap-0.5 px-1 text-center leading-tight">
                {item.name && <span className="line-clamp-2 font-display">{item.name}</span>}
                {!item.name && <span className="line-clamp-2">{item.type_line}</span>}
                {item.stack_size != null && (
                  <span className="text-parchment-100/90">x{item.stack_size}</span>
                )}
              </div>
            )}

            {/* Stack size badge (bottom-left, always visible) */}
            {item.stack_size != null && item.stack_size > 1 && (
              <span className="absolute bottom-0.5 left-0.5 rounded bg-ink-950/80 px-0.5 text-[9px] font-medium text-parchment-100/90">
                {item.stack_size}
              </span>
            )}

            {/* Price badge (bottom-right, always visible) */}
            {price && (
              <span
                className={[
                  "absolute bottom-0.5 right-0.5 rounded px-0.5 text-[9px] font-medium",
                  valuable
                    ? "bg-yellow-900/90 text-yellow-300"
                    : "bg-ink-950/80 text-parchment-100/80",
                ].join(" ")}
              >
                {formatChaos(price.chaos_equiv)}c
              </span>
            )}

            {/* Hover overlay: name + top mods */}
            <div
              className={[
                "pointer-events-none absolute inset-x-0 bottom-0 z-30",
                "flex flex-col gap-0.5 p-1",
                "bg-ink-950/90 opacity-0 transition-opacity group-hover:opacity-100",
                cellH > CELL * 2 ? "max-h-[60%]" : "max-h-full",
              ].join(" ")}
            >
              <span className="line-clamp-1 text-[10px] font-semibold leading-tight text-parchment-50">
                {item.name || item.type_line}
              </span>
              {item.name && (
                <span className="line-clamp-1 text-[9px] text-parchment-100/70">
                  {item.type_line}
                </span>
              )}
              {item.explicit_mods.slice(0, 2).map((mod, i) => (
                <span key={i} className="line-clamp-1 text-[9px] text-rarity-magic/80">
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

function renderBackdrop(w: number, h: number) {
  const cells: React.ReactElement[] = [];
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      cells.push(
        <div
          key={`${x}-${y}`}
          className="absolute border border-ink-800/70"
          style={{ left: x * CELL, top: y * CELL, width: CELL, height: CELL }}
          aria-hidden="true"
        />,
      );
    }
  }
  return cells;
}
