import { useCallback, useMemo, useState } from "react";

import type { ItemRarity } from "@/api/types";
import type { ColumnId, SortDirection } from "./characterTableColumns";
import { DEFAULT_VISIBLE_COLUMN_IDS } from "./characterTableColumns";

const STORAGE_KEY = "poe2b.characterTable.v1";

export type RowCategoryFilter = "equipped" | "skill" | "support" | "jewel" | "other" | "";

export interface CharacterTableFilters {
  q: string;
  rarity: ItemRarity | "";
  minIlvl: number | null;
  identifiedOnly: boolean;
  category: RowCategoryFilter;
  corruptedOnly: boolean;
}

const DEFAULT_FILTERS: CharacterTableFilters = {
  q: "",
  rarity: "",
  minIlvl: null,
  identifiedOnly: false,
  category: "",
  corruptedOnly: false,
};

export interface CharacterTableSort {
  columnId: ColumnId;
  direction: SortDirection;
}

interface StoredState {
  visibleColumnIds: ColumnId[];
  sort: CharacterTableSort;
}

function readStorage(userId?: string | null): StoredState | null {
  try {
    const key = userId ? `${STORAGE_KEY}:${userId}` : STORAGE_KEY;
    const raw = localStorage.getItem(key);
    if (!raw) return null;
    return JSON.parse(raw) as StoredState;
  } catch {
    return null;
  }
}

function writeStorage(state: StoredState, userId?: string | null): void {
  try {
    const key = userId ? `${STORAGE_KEY}:${userId}` : STORAGE_KEY;
    localStorage.setItem(key, JSON.stringify(state));
  } catch {
    // storage quota or private mode — ignore
  }
}

export function useCharacterTableState(userId?: string | null) {
  const [filters, setFilters] = useState<CharacterTableFilters>(DEFAULT_FILTERS);

  const [sort, setSort] = useState<CharacterTableSort>(() => {
    const stored = readStorage(userId);
    return stored?.sort ?? { columnId: "slot", direction: "asc" };
  });

  const [visibleColumnIds, setVisibleColumnIds] = useState<ColumnId[]>(() => {
    const stored = readStorage(userId);
    return stored?.visibleColumnIds ?? [...DEFAULT_VISIBLE_COLUMN_IDS];
  });

  const updateFilters = useCallback((patch: Partial<CharacterTableFilters>) => {
    setFilters((prev) => ({ ...prev, ...patch }));
  }, []);

  const resetFilters = useCallback(() => setFilters(DEFAULT_FILTERS), []);

  const toggleSort = useCallback(
    (colId: ColumnId) => {
      const next: CharacterTableSort =
        sort.columnId === colId
          ? { columnId: colId, direction: sort.direction === "asc" ? "desc" : "asc" }
          : { columnId: colId, direction: "asc" };
      setSort(next);
      writeStorage({ sort: next, visibleColumnIds }, userId);
    },
    [sort, visibleColumnIds, userId],
  );

  const toggleColumn = useCallback(
    (colId: ColumnId) => {
      const next = visibleColumnIds.includes(colId)
        ? visibleColumnIds.filter((id) => id !== colId)
        : [...visibleColumnIds, colId];
      setVisibleColumnIds(next);
      writeStorage({ sort, visibleColumnIds: next }, userId);
    },
    [sort, visibleColumnIds, userId],
  );

  const visibleColumns = useMemo(() => visibleColumnIds, [visibleColumnIds]);

  return {
    filters,
    updateFilters,
    resetFilters,
    sort,
    toggleSort,
    visibleColumnIds: visibleColumns,
    toggleColumn,
  };
}
