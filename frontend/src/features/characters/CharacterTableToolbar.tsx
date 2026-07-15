import { useState } from "react";

import type { ItemRarity } from "@/api/types";
import { ALL_COLUMNS, type ColumnId } from "./characterTableColumns";
import type { CharacterTableFilters, RowCategoryFilter } from "./characterTableState";

const RARITY_OPTIONS: Array<{ value: ItemRarity | ""; label: string }> = [
  { value: "", label: "Any rarity" },
  { value: "Normal", label: "Normal" },
  { value: "Magic", label: "Magic" },
  { value: "Rare", label: "Rare" },
  { value: "Unique", label: "Unique" },
  { value: "Gem", label: "Gem" },
];

const CATEGORY_OPTIONS: Array<{ value: RowCategoryFilter; label: string }> = [
  { value: "", label: "All categories" },
  { value: "equipped", label: "Equipped" },
  { value: "skill", label: "Skill gems" },
  { value: "support", label: "Support gems" },
  { value: "jewel", label: "Jewels" },
  { value: "other", label: "Other" },
];

interface Props {
  filters: CharacterTableFilters;
  onUpdate: (patch: Partial<CharacterTableFilters>) => void;
  onReset: () => void;
  visibleColumnIds: ColumnId[];
  onToggleColumn: (id: ColumnId) => void;
}

export function CharacterTableToolbar({
  filters,
  onUpdate,
  onReset,
  visibleColumnIds,
  onToggleColumn,
}: Props) {
  const [columnPickerOpen, setColumnPickerOpen] = useState(false);

  const hasActiveFilters =
    filters.q ||
    filters.rarity ||
    filters.minIlvl !== null ||
    filters.identifiedOnly ||
    filters.category ||
    filters.corruptedOnly;

  return (
    <div className="flex flex-wrap items-center gap-2 border-b border-ink-700 px-2 py-2">
      {/* Search */}
      <input
        type="search"
        placeholder="Search name, base, mods…"
        value={filters.q}
        onChange={(e) => onUpdate({ q: e.target.value })}
        className="h-7 w-48 rounded-md border border-ink-600 bg-ink-800 px-2 text-sm text-parchment-100 placeholder:text-ui-muted focus:outline-none focus:ring-1 focus:ring-ember-500"
        aria-label="Filter items"
      />

      {/* Rarity */}
      <select
        value={filters.rarity}
        onChange={(e) => onUpdate({ rarity: e.target.value as ItemRarity | "" })}
        className="h-7 rounded-md border border-ink-600 bg-ink-800 px-2 text-sm text-parchment-100 focus:outline-none focus:ring-1 focus:ring-ember-500"
        aria-label="Filter by rarity"
      >
        {RARITY_OPTIONS.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>

      {/* Category */}
      <select
        value={filters.category}
        onChange={(e) => onUpdate({ category: e.target.value as RowCategoryFilter })}
        className="h-7 rounded-md border border-ink-600 bg-ink-800 px-2 text-sm text-parchment-100 focus:outline-none focus:ring-1 focus:ring-ember-500"
        aria-label="Filter by category"
      >
        {CATEGORY_OPTIONS.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>

      {/* Min iLvl */}
      <label className="flex items-center gap-1 text-xs text-ui-muted">
        iLvl ≥
        <input
          type="number"
          min={0}
          max={100}
          value={filters.minIlvl ?? ""}
          onChange={(e) => {
            const v = e.target.value === "" ? null : Number.parseInt(e.target.value, 10);
            onUpdate({ minIlvl: v !== null && !Number.isNaN(v) ? v : null });
          }}
          className="h-7 w-14 rounded-md border border-ink-600 bg-ink-800 px-2 text-sm text-parchment-100 focus:outline-none focus:ring-1 focus:ring-ember-500"
          aria-label="Minimum item level"
        />
      </label>

      {/* Corrupted */}
      <label className="flex cursor-pointer items-center gap-1 text-xs text-ui-muted">
        <input
          type="checkbox"
          checked={filters.corruptedOnly}
          onChange={(e) => onUpdate({ corruptedOnly: e.target.checked })}
          className="rounded accent-ember-500"
        />
        Corrupted
      </label>

      {/* Identified */}
      <label className="flex cursor-pointer items-center gap-1 text-xs text-ui-muted">
        <input
          type="checkbox"
          checked={filters.identifiedOnly}
          onChange={(e) => onUpdate({ identifiedOnly: e.target.checked })}
          className="rounded accent-ember-500"
        />
        Identified
      </label>

      {/* Reset */}
      {hasActiveFilters && (
        <button
          type="button"
          onClick={onReset}
          className="h-7 rounded-md px-2 text-xs text-ember-400 hover:text-ember-200"
        >
          Clear
        </button>
      )}

      <div className="ml-auto relative">
        <button
          type="button"
          onClick={() => setColumnPickerOpen((o) => !o)}
          className="h-7 rounded-md border border-ink-600 bg-ink-800 px-2 text-xs text-ui-muted hover:text-parchment-100"
          aria-label="Show/hide columns"
          aria-expanded={columnPickerOpen}
        >
          Columns
        </button>
        {columnPickerOpen && (
          <div
            role="menu"
            className="absolute right-0 top-full z-20 mt-1 min-w-[160px] rounded-md border border-ink-600 bg-ink-900 p-2 shadow-lg"
          >
            {ALL_COLUMNS.map((col) => (
              <label
                key={col.id}
                className="flex cursor-pointer items-center gap-2 px-1 py-1 text-xs text-parchment-100 hover:text-ember-200"
              >
                <input
                  type="checkbox"
                  checked={visibleColumnIds.includes(col.id)}
                  onChange={() => onToggleColumn(col.id)}
                  className="rounded accent-ember-500"
                />
                {col.label}
              </label>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
