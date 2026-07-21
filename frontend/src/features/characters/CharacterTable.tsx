/**
 * Table view for all character items — supports column picker, sort, and filters.
 * State (sort + visible columns) persists in localStorage.
 */

import { useMemo } from "react";

import type { Item, PriceEstimate } from "@/api/types";
import { itemIconDisplayUrl } from "@/features/items/itemRarityFavicon";
import { type CurrencyChaosPair } from "@/features/items/itemMetrics";
import { ModText } from "@/features/items/ItemModPresentation";
import {
  isCharacterSkillGem,
  isLineageSupportGem,
} from "@/features/characters/characterGemFilter";
import {
  ALL_COLUMNS,
  COLUMN_BY_ID,
  compareRows,
  type RowCategory,
  type TableRow,
} from "@/features/characters/characterTableColumns";
import { CharacterTableToolbar } from "@/features/characters/CharacterTableToolbar";
import { useCharacterTableState } from "@/features/characters/characterTableState";

const SLOT_LABELS: Record<string, string> = {
  Helm: "Helm",
  Amulet: "Amulet",
  Weapon: "Main hand",
  Weapon2: "Weapon swap",
  Offhand: "Off hand",
  Offhand2: "Off hand swap",
  BodyArmour: "Body armour",
  Gloves: "Gloves",
  Ring: "Ring (L)",
  Ring2: "Ring (R)",
  Belt: "Belt",
  Boots: "Boots",
  Charm: "Charm",
  PassiveJewels: "Jewel",
  SkillSlots: "Skill gem",
  AscendancySkills: "Ascendancy skill",
};

function slotLabel(item: Item): string {
  if (item.inventory_id) {
    return SLOT_LABELS[item.inventory_id] ?? item.inventory_id;
  }
  if (isCharacterSkillGem(item)) return "Skill gem";
  if (isLineageSupportGem(item)) return "Support gem";
  return "—";
}

function itemCategory(_item: Item, bucketName: RowCategory): RowCategory {
  return bucketName;
}

export interface CharacterTableProps {
  equipped: Item[];
  gems: Item[];
  supportGems?: Item[];
  jewels: Item[];
  charms?: Item[];
  other: Item[];
  selectedItemId: string | null;
  onSelect: (item: Item) => void;
  prices?: Record<string, PriceEstimate | null>;
  valuableThreshold?: number;
  currencyChaos?: CurrencyChaosPair | null;
  userId?: string | null;
}

export function CharacterTable({
  equipped,
  gems,
  supportGems = [],
  jewels,
  charms = [],
  other,
  selectedItemId,
  onSelect,
  prices,
  valuableThreshold,
  currencyChaos,
  userId,
}: CharacterTableProps) {
  const { filters, updateFilters, resetFilters, sort, toggleSort, visibleColumnIds, toggleColumn } =
    useCharacterTableState(userId);

  // Build tagged rows from bucket arrays
  const allRows = useMemo<TableRow[]>(() => {
    const rows: TableRow[] = [];
    const push = (items: Item[], cat: RowCategory) => {
      for (const item of items) {
        rows.push({
          item,
          category: itemCategory(item, cat),
          price: prices?.[item.id],
          slotLabel: slotLabel(item),
          currencyChaos,
        });
      }
    };
    push(equipped, "equipped");
    push(gems, "skill");
    push(supportGems, "support");
    push(jewels, "jewel");
    push(charms, "charm");
    push(other, "other");
    return rows;
  }, [equipped, gems, supportGems, jewels, charms, other, prices, currencyChaos]);

  // Filter
  const filteredRows = useMemo(() => {
    const needle = filters.q.trim().toLowerCase();
    return allRows.filter((row) => {
      const { item } = row;
      if (filters.rarity && item.rarity !== filters.rarity) return false;
      if (filters.category && row.category !== filters.category) return false;
      if (filters.minIlvl !== null && (item.ilvl ?? 0) < filters.minIlvl) return false;
      if (filters.identifiedOnly && !item.identified) return false;
      if (filters.corruptedOnly && !item.corrupted) return false;
      if (!needle) return true;
      const haystack = [
        item.name,
        item.type_line,
        item.base_type,
        ...item.explicit_mods,
        ...item.implicit_mods,
      ]
        .join(" ")
        .toLowerCase();
      return haystack.includes(needle);
    });
  }, [allRows, filters]);

  // Sort
  const sortedRows = useMemo(() => {
    const col = COLUMN_BY_ID[sort.columnId];
    if (!col.sortKey) return filteredRows;
    return [...filteredRows].sort((a, b) => compareRows(a, b, sort.columnId, sort.direction));
  }, [filteredRows, sort]);

  // Derive grid template from visible columns
  const gridCols = useMemo(() => {
    const visible = ALL_COLUMNS.filter((c) => visibleColumnIds.includes(c.id));
    return visible.map((c) => c.width).join(" ");
  }, [visibleColumnIds]);

  if (allRows.length === 0) {
    return <p className="text-sm text-ui-muted">No items equipped.</p>;
  }

  return (
    <div className="flex flex-col rounded-md border border-ink-700 bg-ink-950/70">
      <CharacterTableToolbar
        filters={filters}
        onUpdate={updateFilters}
        onReset={resetFilters}
        visibleColumnIds={visibleColumnIds}
        onToggleColumn={toggleColumn}
      />

      <div className="overflow-auto" role="grid" aria-label="Equipped items">
        {/* Header */}
        <div
          className="grid gap-2 border-b border-ink-700 bg-ink-900/95 px-3 py-2 text-[11px] uppercase tracking-wide text-ui-muted"
          style={{ gridTemplateColumns: gridCols }}
          role="row"
        >
          {ALL_COLUMNS.filter((c) => visibleColumnIds.includes(c.id)).map((col) => (
            <button
              key={col.id}
              type="button"
              className={[
                "text-left",
                col.sortable
                  ? "cursor-pointer hover:text-parchment-100 focus:outline-none focus-visible:text-parchment-100"
                  : "cursor-default",
                sort.columnId === col.id ? "text-parchment-200" : "",
              ]
                .filter(Boolean)
                .join(" ")}
              onClick={() => col.sortable && toggleSort(col.id)}
              disabled={!col.sortable}
              role="columnheader"
              aria-sort={
                sort.columnId === col.id
                  ? sort.direction === "asc"
                    ? "ascending"
                    : "descending"
                  : undefined
              }
            >
              {col.label}
              {sort.columnId === col.id ? (sort.direction === "asc" ? " ↑" : " ↓") : null}
            </button>
          ))}
        </div>

        {/* Rows */}
        {sortedRows.length === 0 ? (
          <p className="px-3 py-4 text-sm text-ui-muted">No items match the current filters.</p>
        ) : (
          sortedRows.map((row) => {
            const { item } = row;
            const isSelected = item.id === selectedItemId;
            const valuable =
              row.price && valuableThreshold != null && row.price.chaos_equiv >= valuableThreshold;

            return (
              <button
                type="button"
                key={item.id}
                onClick={() => onSelect(item)}
                className={[
                  "grid w-full items-center gap-2 px-3 py-2 text-left text-sm",
                  "border-b border-ink-800 transition hover:bg-ink-800/70 focus:outline-none focus-visible:bg-ink-800 focus-visible:ring-2 focus-visible:ring-ember-400/70 focus-visible:ring-inset",
                  isSelected ? "bg-ember-500/10 text-ember-200" : "text-parchment-100",
                ].join(" ")}
                style={{ gridTemplateColumns: gridCols }}
                role="row"
                aria-selected={isSelected}
                data-testid="char-table-row"
              >
                {ALL_COLUMNS.filter((c) => visibleColumnIds.includes(c.id)).map((col) => {
                  if (col.id === "name") {
                    return (
                      <span key={col.id} className="flex items-center gap-1.5 truncate">
                        <img
                          src={itemIconDisplayUrl(item)}
                          alt=""
                          className="h-5 w-5 shrink-0 object-contain"
                          loading="lazy"
                        />
                        <span className="truncate">{item.name || item.type_line || "—"}</span>
                      </span>
                    );
                  }
                  if (col.id === "mods" || col.id === "implicits") {
                    const mods = col.id === "mods" ? item.explicit_mods : item.implicit_mods;
                    return (
                      <span key={col.id} className="truncate text-xs text-rarity-magic/90">
                        {mods.slice(0, 2).map((m, i) => (
                          <span key={i}>
                            {i > 0 ? " · " : null}
                            <ModText raw={m} />
                          </span>
                        ))}
                      </span>
                    );
                  }
                  if (col.id === "price") {
                    return (
                      <span
                        key={col.id}
                        className={
                          valuable
                            ? "truncate text-xs font-semibold text-yellow-300"
                            : "truncate text-xs text-parchment-100/90"
                        }
                      >
                        {col.display(row)}
                      </span>
                    );
                  }
                  return (
                    <span key={col.id} className="truncate text-xs text-ui-muted">
                      {col.display(row)}
                    </span>
                  );
                })}
              </button>
            );
          })
        )}
      </div>
    </div>
  );
}
