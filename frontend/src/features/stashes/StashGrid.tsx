import type { Item, ItemRarity, PriceEstimate } from "@/api/types";
import { formatChaos } from "@/features/items/PriceBadge";

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
        return (
          <button
            type="button"
            key={item.id}
            onClick={() => onSelect(item)}
            className={[
              "absolute overflow-hidden border text-[10px] transition",
              "focus:outline-none focus-visible:ring-2 focus-visible:ring-ember-400",
              "hover:z-10 hover:ring-2 hover:ring-ember-400",
              selected ? "z-10 ring-2 ring-ember-400" : "",
              highlighted ? "outline outline-2 outline-emerald-400" : "",
              rarityClass,
            ]
              .filter(Boolean)
              .join(" ")}
            style={{
              left: item.x * CELL,
              top: item.y * CELL,
              width: item.w * CELL,
              height: item.h * CELL,
            }}
            aria-label={`${item.name || item.type_line} at ${item.x},${item.y}`}
            title={`${item.name || ""}\n${item.type_line}`.trim()}
            data-testid="stash-cell"
          >
            <div className="flex h-full w-full flex-col items-center justify-center gap-0.5 px-1 text-center leading-tight">
              {item.name && <span className="line-clamp-2 font-display">{item.name}</span>}
              {!item.name && <span className="line-clamp-2">{item.type_line}</span>}
              {item.stack_size != null && (
                <span className="text-parchment-100/90">x{item.stack_size}</span>
              )}
              {price && (
                <span
                  className={
                    valuable
                      ? "text-[10px] font-medium text-emerald-300"
                      : "text-[10px] text-parchment-100/80"
                  }
                >
                  ◈ {formatChaos(price.chaos_equiv)}c
                </span>
              )}
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
