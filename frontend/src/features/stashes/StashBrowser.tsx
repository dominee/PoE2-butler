import { useEffect, useMemo, useState } from "react";

import {
  useActivity,
  usePriceLookup,
  useRefreshStashes,
  useStashList,
  useStashSearch,
  useStashTab,
} from "@/api/hooks";
import type { Item, ItemRarity } from "@/api/types";
import { ItemCard } from "@/features/items/ItemCard";
import { useUIStore } from "@/store/uiStore";

import { applyFilters, useStashFilters } from "./filters";
import { CurrencyTabGrid } from "./CurrencyTabGrid";
import { StashGrid } from "./StashGrid";
import { StashIconGrid } from "./StashIconGrid";
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

  const [searchAllTabs, setSearchAllTabs] = useState(false);

  const tabsQ = useStashList(league);
  const tabQ = useStashTab(league, selectedTab);
  const refresh = useRefreshStashes();
  const { filters, update, reset } = useStashFilters();
  const activityQ = useActivity(league);

  // Cross-tab search — enabled when the user opts in and has ≥ 2 chars in query.
  const crossTabActive = searchAllTabs && filters.q.trim().length >= 2;
  const searchQ = useStashSearch(crossTabActive ? league : null, filters.q.trim());

  useEffect(() => {
    if (!selectedTab && tabsQ.data?.tabs.length) {
      setSelectedTab(tabsQ.data.tabs[0]!.id);
    }
  }, [tabsQ.data, selectedTab, setSelectedTab]);

  const items = useMemo(() => tabQ.data?.items ?? [], [tabQ.data?.items]);
  const filtered = useMemo(() => applyFilters(items, filters), [items, filters]);
  const pricesQ = usePriceLookup(league, items);
  const prices = useMemo(() => pricesQ.data?.prices ?? {}, [pricesQ.data?.prices]);
  const valuableIds = useMemo(() => {
    if (valuableThreshold == null) return undefined;
    const ids = new Set<string>();
    for (const item of items) {
      const p = prices[item.id];
      if (p && p.chaos_equiv >= valuableThreshold) ids.add(item.id);
    }
    return ids;
  }, [items, prices, valuableThreshold]);

  const activityMap = useMemo(() => {
    const map = new Map<string, "new" | "changed">();
    for (const entry of activityQ.data?.entries ?? []) {
      for (const item of entry.new_items) map.set(item.id, "new");
      for (const { new: item } of entry.changed_items) map.set(item.id, "changed");
    }
    return map;
  }, [activityQ.data]);

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
          selected={crossTabActive ? null : selectedTab}
          onSelect={(id) => {
            setSearchAllTabs(false);
            setSelectedTab(id);
          }}
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
              title="Positional stash grid with item icons"
            >
              Grid
            </button>
            <button
              type="button"
              role="radio"
              aria-checked={layout === "icons"}
              onClick={() => setLayout("icons")}
              className={layoutBtn(layout === "icons")}
              title="Large icon gallery"
            >
              Icons
            </button>
            <button
              type="button"
              role="radio"
              aria-checked={layout === "table"}
              onClick={() => setLayout("table")}
              className={layoutBtn(layout === "table")}
              title="Sortable table view"
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
          onChange={(event) => update({ rarity: event.target.value as StashFilterRarity })}
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
        {/* Cross-tab search toggle — only shown when there is a query */}
        {filters.q.trim().length >= 2 && (
          <label
            className={[
              "flex cursor-pointer items-center gap-1 rounded-md border px-2 py-0.5 text-xs transition",
              searchAllTabs
                ? "border-ember-400 bg-ember-500/10 text-ember-200"
                : "border-ink-700 text-parchment-100/80 hover:border-ember-400/60",
            ].join(" ")}
            title="Search across all stash tabs (uses backend)"
          >
            <input
              type="checkbox"
              className="sr-only"
              checked={searchAllTabs}
              onChange={(e) => setSearchAllTabs(e.target.checked)}
            />
            All tabs
          </label>
        )}
        <button
          type="button"
          className="btn-ghost text-xs"
          onClick={() => {
            reset();
            setSearchAllTabs(false);
          }}
          aria-label="Clear filters"
        >
          Clear
        </button>
        {!crossTabActive && (
          <span className="ml-auto text-xs text-ink-400" aria-live="polite" aria-atomic="true">
            Showing {filtered.length} / {items.length}
          </span>
        )}
        {crossTabActive && searchQ.data && (
          <span className="ml-auto text-xs text-ink-400" aria-live="polite">
            {searchQ.data.total_items} items across {searchQ.data.results.length} tabs
          </span>
        )}
      </div>

      {/* ── Cross-tab search results ───────────────────────────────────────── */}
      {crossTabActive && (
        <div className="flex flex-col gap-4 overflow-y-auto">
          {searchQ.isLoading && <p className="text-ink-500">Searching all tabs&hellip;</p>}
          {searchQ.data?.results.length === 0 && (
            <p className="text-sm text-ink-500">
              No items found matching &ldquo;{searchQ.data.query}&rdquo; in any tab.
            </p>
          )}
          {searchQ.data?.results.map((group) => (
            <div key={group.tab_id}>
              <h3 className="mb-1 text-xs font-semibold uppercase tracking-widest text-ink-400">
                {group.tab_name}{" "}
                <span className="text-ink-600">({group.items.length})</span>
              </h3>
              <div className="grid grid-cols-[repeat(auto-fill,minmax(200px,1fr))] gap-2">
                {group.items.map((item) => (
                  <ItemCard
                    key={item.id}
                    item={item}
                    selected={selectedItemId === item.id}
                    onClick={onSelectItem}
                    activityStatus={activityMap.get(item.id)}
                  />
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* ── Single-tab view ────────────────────────────────────────────────── */}
      {!crossTabActive && (
        <>
          {tabQ.isLoading && <p className="text-ink-500">Loading tab&hellip;</p>}
          {tabQ.isError && (
            <p className="text-red-400">
              Couldn&apos;t load this tab. Try refreshing the stash.
            </p>
          )}
          {tabQ.data && layout === "grid" && (
            <div className="overflow-auto">
              {tabQ.data.tab.type === "CurrencyStash" ? (
                <CurrencyTabGrid
                  items={filtered}
                  selectedItemId={selectedItemId}
                  onSelect={onSelectItem}
                  prices={prices}
                  valuableThreshold={valuableThreshold}
                  activityMap={activityMap}
                />
              ) : (
                <StashGrid
                  tabType={tabQ.data.tab.type}
                  items={filtered}
                  selectedItemId={selectedItemId}
                  onSelect={onSelectItem}
                  highlightIds={valuableIds}
                  prices={prices}
                  valuableThreshold={valuableThreshold}
                  activityMap={activityMap}
                />
              )}
            </div>
          )}
          {tabQ.data && layout === "icons" && (
            <div className="overflow-auto">
              <StashIconGrid
                items={filtered}
                selectedItemId={selectedItemId}
                onSelect={onSelectItem}
                highlightIds={valuableIds}
                prices={prices}
                valuableThreshold={valuableThreshold}
                activityMap={activityMap}
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
              activityMap={activityMap}
            />
          )}
        </>
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

