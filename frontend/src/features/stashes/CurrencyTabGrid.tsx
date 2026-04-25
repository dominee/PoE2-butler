/**
 * Dedicated grid renderer for Currency stash tabs.
 *
 * Uses the positional layout from the GGG API (x,y) but renders larger cells
 * so that item icons are the primary focus.  Stack size and total value
 * (price × stack) are shown prominently beneath each icon.
 */

import type { Item, PriceEstimate } from "@/api/types";
import { formatChaos } from "@/features/items/itemMetrics";

export interface CurrencyTabGridProps {
  items: Item[];
  selectedItemId: string | null;
  onSelect: (item: Item) => void;
  prices?: Record<string, PriceEstimate | null>;
  valuableThreshold?: number;
  activityMap?: Map<string, "new" | "changed">;
}

const CELL = 56;
const COLS = 12;
const ROWS = 12;

export function CurrencyTabGrid({
  items,
  selectedItemId,
  onSelect,
  prices,
  valuableThreshold,
  activityMap,
}: CurrencyTabGridProps) {
  return (
    <div
      className="relative border border-ink-700 bg-ink-950/70"
      style={{ width: COLS * CELL, height: ROWS * CELL }}
      role="grid"
      aria-label="Currency stash tab"
    >
      {renderBackdrop()}
      {items.map((item) => {
        if (item.x == null || item.y == null) return null;
        const selected = item.id === selectedItemId;
        const price = prices?.[item.id];
        const totalValue =
          price && item.stack_size != null ? price.chaos_equiv * item.stack_size : null;
        const valuable =
          totalValue != null && valuableThreshold != null && totalValue >= valuableThreshold;
        const activityStatus = activityMap?.get(item.id);

        return (
          <button
            type="button"
            key={item.id}
            onClick={() => onSelect(item)}
            className={[
              "group absolute flex flex-col items-center justify-start overflow-hidden",
              "border border-rarity-currency/20 bg-ink-900/50 pb-0.5 transition",
              "focus:outline-none focus-visible:ring-2 focus-visible:ring-ember-400",
              "hover:z-10 hover:border-rarity-currency/60 hover:bg-ink-800/80",
              selected ? "z-10 ring-2 ring-ember-400" : "",
              valuable ? "outline outline-2 outline-yellow-400" : "",
            ]
              .filter(Boolean)
              .join(" ")}
            style={{
              left: item.x * CELL,
              top: item.y * CELL,
              width: item.w * CELL,
              height: item.h * CELL,
            }}
            aria-label={item.type_line}
            title={item.type_line}
            data-testid="currency-cell"
          >
            {/* Activity dot */}
            {activityStatus && (
              <span
                className={[
                  "absolute right-0.5 top-0.5 z-10 h-1.5 w-1.5 rounded-full",
                  activityStatus === "new" ? "bg-emerald-400" : "bg-amber-400",
                ].join(" ")}
              />
            )}

            {/* Icon */}
            {item.icon ? (
              <img
                src={item.icon}
                alt={item.type_line}
                className="h-3/5 w-full object-contain pt-1"
                loading="lazy"
              />
            ) : (
              <div className="flex h-3/5 w-full items-center justify-center px-0.5 text-center text-[10px] leading-tight text-rarity-currency">
                {item.type_line}
              </div>
            )}

            {/* Stack size */}
            {item.stack_size != null && (
              <span className="mt-0.5 text-[11px] font-semibold text-rarity-currency">
                ×{item.stack_size.toLocaleString()}
              </span>
            )}

            {/* Total value */}
            {price && (
              <span
                className={[
                  "text-[9px]",
                  valuable ? "text-yellow-300" : "text-parchment-100/60",
                ].join(" ")}
              >
                {totalValue != null
                  ? `${formatChaos(totalValue)}c total`
                  : `${formatChaos(price.chaos_equiv)}c`}
              </span>
            )}

            {/* Hover label */}
            <div className="pointer-events-none absolute inset-x-0 bottom-0 z-30 translate-y-full rounded-b bg-ink-950/95 px-1 py-0.5 text-center text-[9px] leading-tight text-parchment-50 opacity-0 transition-all group-hover:translate-y-0 group-hover:opacity-100">
              {item.type_line}
            </div>
          </button>
        );
      })}
    </div>
  );
}

function renderBackdrop() {
  const cells: React.ReactElement[] = [];
  for (let y = 0; y < ROWS; y++) {
    for (let x = 0; x < COLS; x++) {
      cells.push(
        <div
          key={`${x}-${y}`}
          className="absolute border border-ink-800/40"
          style={{ left: x * CELL, top: y * CELL, width: CELL, height: CELL }}
          aria-hidden="true"
        />,
      );
    }
  }
  return cells;
}
