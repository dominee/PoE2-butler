import { useEffect, useRef, useState } from "react";

import type { Item, PriceEstimate } from "@/api/types";
import { formatChaos } from "@/features/items/itemMetrics";

export interface StashTableProps {
  items: Item[];
  selectedItemId: string | null;
  onSelect: (item: Item) => void;
  highlightIds?: Set<string>;
  prices?: Record<string, PriceEstimate | null>;
  valuableThreshold?: number;
  activityMap?: Map<string, "new" | "changed">;
}

const ROW_HEIGHT = 36;
const OVERSCAN = 6;

/**
 * Lightweight virtualized table (no external deps). Rendering only the rows
 * visible within the scroll viewport keeps 5000+ item stashes snappy on the
 * 1 GB VM class machines we target.
 */
export function StashTable({
  items,
  selectedItemId,
  onSelect,
  highlightIds,
  prices,
  valuableThreshold,
  activityMap,
}: StashTableProps) {
  const ref = useRef<HTMLDivElement>(null);
  const [scrollTop, setScrollTop] = useState(0);
  const [height, setHeight] = useState(400);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const onScroll = () => setScrollTop(el.scrollTop);
    el.addEventListener("scroll", onScroll, { passive: true });
    const ro = new ResizeObserver(() => {
      setHeight(el.clientHeight);
    });
    ro.observe(el);
    setHeight(el.clientHeight);
    return () => {
      el.removeEventListener("scroll", onScroll);
      ro.disconnect();
    };
  }, []);

  const total = items.length;
  const start = Math.max(0, Math.floor(scrollTop / ROW_HEIGHT) - OVERSCAN);
  const visibleCount = Math.ceil(height / ROW_HEIGHT) + OVERSCAN * 2;
  const end = Math.min(total, start + visibleCount);
  const rows = items.slice(start, end);

  return (
    <div
      ref={ref}
      className="relative h-[70vh] min-h-[360px] overflow-auto rounded-md border border-ink-700 bg-ink-950/70"
      role="grid"
      aria-rowcount={total}
      aria-label="Stash items"
    >
      <div
        className="sticky top-0 z-10 grid grid-cols-[16px_minmax(140px,1.5fr)_minmax(120px,1fr)_80px_60px_70px_1fr] gap-2 border-b border-ink-700 bg-ink-900/95 px-3 py-2 text-[11px] uppercase tracking-wide text-ink-400"
        role="row"
      >
        <span aria-label="Activity status" />
        <span>Name</span>
        <span>Base type</span>
        <span>Rarity</span>
        <span>iLvl</span>
        <span>Price</span>
        <span>Mods</span>
      </div>
      <div style={{ height: total * ROW_HEIGHT, position: "relative" }}>
        <div style={{ position: "absolute", top: start * ROW_HEIGHT, left: 0, right: 0 }}>
          {rows.map((item) => {
            const isSelected = item.id === selectedItemId;
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
                style={{ height: ROW_HEIGHT }}
                className={[
                  "grid w-full grid-cols-[16px_minmax(140px,1.5fr)_minmax(120px,1fr)_80px_60px_70px_1fr] items-center gap-2 px-3 text-left text-sm",
                  "border-b border-ink-800 transition hover:bg-ink-800/70 focus:outline-none focus-visible:bg-ink-800",
                  isSelected ? "bg-ember-500/10 text-ember-200" : "text-parchment-100",
                  highlighted ? "ring-1 ring-yellow-400/70" : "",
                ].join(" ")}
                role="row"
                aria-selected={isSelected}
                data-testid="stash-row"
              >
                <span className="flex items-center justify-center">
                  {activityStatus && (
                    <span
                      className={[
                        "h-1.5 w-1.5 rounded-full",
                        activityStatus === "new" ? "bg-emerald-400" : "bg-amber-400",
                      ].join(" ")}
                      aria-label={activityStatus === "new" ? "New item" : "Changed item"}
                    />
                  )}
                </span>
                <span className="truncate">{item.name || "—"}</span>
                <span className="truncate text-parchment-100/80">{item.base_type}</span>
                <span className="text-xs uppercase tracking-wide text-ink-400">
                  {item.rarity}
                </span>
                <span className="text-ink-400">{item.ilvl ?? "—"}</span>
                <span
                  className={
                    valuable
                      ? "text-xs font-semibold text-yellow-300"
                      : "text-xs text-parchment-100/90"
                  }
                >
                  {price ? `${formatChaos(price.chaos_equiv)}c` : "—"}
                </span>
                <span className="truncate text-xs text-rarity-magic/90">
                  {item.explicit_mods.slice(0, 2).join(" · ")}
                </span>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
