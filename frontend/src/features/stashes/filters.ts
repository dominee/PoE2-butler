import { useCallback, useMemo } from "react";
import { useSearchParams } from "react-router-dom";

import type { Item, ItemRarity } from "@/api/types";

export interface StashFilters {
  q: string;
  rarity: ItemRarity | "";
  minIlvl: number | null;
  identifiedOnly: boolean;
}

const DEFAULT_FILTERS: StashFilters = {
  q: "",
  rarity: "",
  minIlvl: null,
  identifiedOnly: false,
};

export function useStashFilters() {
  const [params, setParams] = useSearchParams();

  const filters = useMemo<StashFilters>(() => {
    const q = params.get("q") ?? "";
    const rarity = (params.get("rarity") ?? "") as StashFilters["rarity"];
    const minIlvlRaw = params.get("ilvl");
    const minIlvl = minIlvlRaw ? Number.parseInt(minIlvlRaw, 10) : null;
    const identifiedOnly = params.get("id") === "1";
    return { q, rarity, minIlvl: Number.isNaN(minIlvl) ? null : minIlvl, identifiedOnly };
  }, [params]);

  const update = useCallback(
    (patch: Partial<StashFilters>) => {
      const next = { ...filters, ...patch };
      setParams(
        (prev) => {
          const copy = new URLSearchParams(prev);
          writeFilter(copy, "q", next.q);
          writeFilter(copy, "rarity", next.rarity);
          writeFilter(copy, "ilvl", next.minIlvl === null ? "" : String(next.minIlvl));
          writeFilter(copy, "id", next.identifiedOnly ? "1" : "");
          return copy;
        },
        { replace: true },
      );
    },
    [filters, setParams],
  );

  const reset = useCallback(() => {
    setParams(
      (prev) => {
        const copy = new URLSearchParams(prev);
        ["q", "rarity", "ilvl", "id"].forEach((k) => copy.delete(k));
        return copy;
      },
      { replace: true },
    );
  }, [setParams]);

  return { filters, update, reset, defaults: DEFAULT_FILTERS };
}

function writeFilter(params: URLSearchParams, key: string, value: string): void {
  if (!value) params.delete(key);
  else params.set(key, value);
}

export function applyFilters(items: Item[], filters: StashFilters): Item[] {
  const needle = filters.q.trim().toLowerCase();
  return items.filter((item) => {
    if (filters.rarity && item.rarity !== filters.rarity) return false;
    if (filters.minIlvl !== null && (item.ilvl ?? 0) < filters.minIlvl) return false;
    if (filters.identifiedOnly && !item.identified) return false;
    if (!needle) return true;

    const haystack = [
      item.name,
      item.type_line,
      item.base_type,
      ...item.explicit_mods,
      ...item.implicit_mods,
      ...item.rune_mods,
      ...item.enchant_mods,
      ...item.crafted_mods,
    ]
      .join(" \u0001 ")
      .toLowerCase();
    return haystack.includes(needle);
  });
}
