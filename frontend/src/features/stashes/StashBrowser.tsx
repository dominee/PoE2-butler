import { useEffect, useMemo } from "react";

import {
  usePriceLookup,
  useRefreshStashes,
  useStashList,
  useStashTab,
} from "@/api/hooks";
import type { Item, ItemRarity } from "@/api/types";
import { useUIStore } from "@/store/uiStore";

import { applyFilters, useStashFilters } from "./filters";
import { StashGrid } from "./StashGrid";
import { StashTable } from "./StashTable";
import { TabStrip } from "./TabStrip";

export interface StashBrowserProps {
  league: string | null;
  selectedItemId: string | null;
  onSelectItem: (item: Item) => void;
  valuableThreshold?: number;
}

const RARITY_OPTIONS: { value: ItemRarity | ""; label: string }[] = [
  { value: "", label: "Any rarity" },
  { value: "Normal", label: "Normal" },
  { value: "Magic", label: "Magic" },
  { value: "Rare", label: "Rare" },
  { value: "Unique", label: "Unique" },
  { value: "Currency", label: "Currency" },
  { value: "Gem", label: "Gem" },
];

export function StashBrowser({
  league,
  selectedItemId,
  onSelectItem,
  valuableThreshold,
}: StashBrowserProps) {
  const selectedTab = useUIStore((state) => state.selectedTab);
  const setSelectedTab = useUIStore((state) => state.setSelectedTab);
  const layout = useUIStore((state) => state.stashLayout);
  const setLayout = useUIStore((state) => state.setStashLayout);

  const tabsQ = useStashList(league);
  const tabQ = useStashTab(league, selectedTab);
  const refresh = useRefreshStashes();
  const { filters, update, reset } = useStashFilters();

  useEffect(() => {
    if (!selectedTab && tabsQ.data?.tabs.length) {
      setSelectedTab(tabsQ.data.tabs[0]!.id);
    }
  }, [tabsQ.data, selectedTab, setSelectedTab]);

  const items = tabQ.data?.items ?? [];
  const filtered = useMemo(() => applyFilters(items, filters), [items, filters]);
  const pricesQ = usePriceLookup(league, items);
  const prices = pricesQ.data?.prices ?? {};
  const valuableIds = useMemo(() => {
    if (valuableThreshold == null) return undefined;
    const ids = new Set<string>();
    for (const item of items) {
      const p = prices[item.id];
      if (p && p.chaos_equiv >= valuableThreshold) ids.add(item.id);
    }
    return ids;
  }, [items, prices, valuableThreshold]);

  if (!league) {
    return (
      <section aria-label="Stash" className="space-y-3">
        <p className="text-ink-500">Select a league to browse stash tabs.</p>
      </section>
    );
  }

  return (
    <section aria-label="Stash" className="flex min-h-0 flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <TabStrip
          tabs={tabsQ.data?.tabs ?? []}
          selected={selectedTab}
          onSelect={setSelectedTab}
        />
        <div className="ml-auto flex items-center gap-2">
          <div
            className="inline-flex rounded-md border border-ink-700 bg-ink-800 text-xs"
            role="radiogroup"
            aria-label="Stash layout"
          >
            <button
              type="button"
              role="radio"
              aria-checked={layout === "grid"}
              onClick={() => setLayout("grid")}
              className={layoutBtn(layout === "grid")}
            >
              Grid
            </button>
            <button
              type="button"
              role="radio"
              aria-checked={layout === "table"}
              onClick={() => setLayout("table")}
              className={layoutBtn(layout === "table")}
            >
              Table
            </button>
          </div>
          <button
            type="button"
            className="btn-ghost text-sm"
            onClick={() => refresh.mutate({ league })}
            disabled={refresh.isPending}
            aria-label="Refresh stash tabs"
          >
            {refresh.isPending ? "Refreshing\u2026" : "Refresh stash"}
          </button>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2 rounded-md border border-ink-800 bg-ink-900/60 px-3 py-2">
        <label className="sr-only" htmlFor="stash-search">
          Search items
        </label>
        <input
          id="stash-search"
          value={filters.q}
          onChange={(event) => update({ q: event.target.value })}
          placeholder="Search name, base or mod..."
          className="min-w-[220px] flex-1 rounded-md border border-ink-700 bg-ink-800 px-2 py-1 text-sm"
          autoComplete="off"
        />
        <select
          value={filters.rarity}
          onChange={(event) =>
            update({ rarity: event.target.value as StashFilterRarity })
          }
          className="rounded-md border border-ink-700 bg-ink-800 px-2 py-1 text-sm"
          aria-label="Rarity filter"
        >
          {RARITY_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
        <label className="flex items-center gap-1 text-xs text-parchment-100/80">
          Min iLvl
          <input
            type="number"
            min={0}
            max={100}
            value={filters.minIlvl ?? ""}
            onChange={(event) =>
              update({
                minIlvl: event.target.value ? Number.parseInt(event.target.value, 10) : null,
              })
            }
            className="w-16 rounded-md border border-ink-700 bg-ink-800 px-2 py-1"
          />
        </label>
        <label className="flex items-center gap-1 text-xs text-parchment-100/80">
          <input
            type="checkbox"
            checked={filters.identifiedOnly}
            onChange={(event) => update({ identifiedOnly: event.target.checked })}
          />
          Identified only
        </label>
        <button
          type="button"
          className="btn-ghost text-xs"
          onClick={reset}
          aria-label="Clear filters"
        >
          Clear
        </button>
        <span
          className="ml-auto text-xs text-ink-400"
          aria-live="polite"
          aria-atomic="true"
        >
          Showing {filtered.length} / {items.length}
        </span>
      </div>

      {tabQ.isLoading && <p className="text-ink-500">Loading tab&hellip;</p>}
      {tabQ.isError && (
        <p className="text-red-400">
          Couldn&apos;t load this tab. Try refreshing the stash.
        </p>
      )}
      {tabQ.data && layout === "grid" && (
        <div className="overflow-auto">
          <StashGrid
            tabType={tabQ.data.tab.type}
            items={filtered}
            selectedItemId={selectedItemId}
            onSelect={onSelectItem}
            highlightIds={valuableIds}
            prices={prices}
            valuableThreshold={valuableThreshold}
          />
        </div>
      )}
      {tabQ.data && layout === "table" && (
        <StashTable
          items={filtered}
          selectedItemId={selectedItemId}
          onSelect={onSelectItem}
          highlightIds={valuableIds}
          prices={prices}
          valuableThreshold={valuableThreshold}
        />
      )}
    </section>
  );
}

type StashFilterRarity = ItemRarity | "";

function layoutBtn(active: boolean): string {
  return [
    "px-3 py-1 transition",
    active ? "bg-ember-500/10 text-ember-200" : "text-parchment-100",
  ].join(" ");
}
