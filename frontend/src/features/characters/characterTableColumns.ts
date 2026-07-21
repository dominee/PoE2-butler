import type { Item, PriceEstimate } from "@/api/types";
import type { CurrencyChaosPair } from "@/features/items/itemMetrics";
import { formatChaos, formatChaosAsDivExLine } from "@/features/items/itemMetrics";

export type ColumnId =
  | "slot"
  | "name"
  | "base_type"
  | "ilvl"
  | "price"
  | "mods"
  | "rarity"
  | "category"
  | "sockets"
  | "corrupted"
  | "identified"
  | "implicits"
  | "runeforged";

export type SortDirection = "asc" | "desc";

export interface ColumnDef {
  id: ColumnId;
  label: string;
  /** Approximate CSS grid width token (e.g. "80px", "minmax(140px,2fr)"). */
  width: string;
  defaultVisible: boolean;
  sortable: boolean;
  /** Extract a primitive sort key from a row. */
  sortKey?: (row: TableRow) => string | number;
  /** Render the cell value as a string (used for display; the table renders actual components). */
  display: (row: TableRow) => string;
}

export type RowCategory = "equipped" | "skill" | "support" | "jewel" | "charm" | "other";

export interface TableRow {
  item: Item;
  category: RowCategory;
  price: PriceEstimate | null | undefined;
  slotLabel: string;
  currencyChaos: CurrencyChaosPair | null | undefined;
}

export const ALL_COLUMNS: readonly ColumnDef[] = [
  {
    id: "slot",
    label: "Slot",
    width: "120px",
    defaultVisible: true,
    sortable: true,
    sortKey: (r) => r.slotLabel,
    display: (r) => r.slotLabel,
  },
  {
    id: "name",
    label: "Name",
    width: "minmax(140px,2fr)",
    defaultVisible: true,
    sortable: true,
    sortKey: (r) => r.item.name || r.item.type_line,
    display: (r) => r.item.name || r.item.type_line,
  },
  {
    id: "base_type",
    label: "Base type",
    width: "minmax(110px,1fr)",
    defaultVisible: true,
    sortable: true,
    sortKey: (r) => r.item.base_type,
    display: (r) => r.item.base_type,
  },
  {
    id: "ilvl",
    label: "iLvl",
    width: "60px",
    defaultVisible: true,
    sortable: true,
    sortKey: (r) => r.item.ilvl ?? -1,
    display: (r) => String(r.item.ilvl ?? "—"),
  },
  {
    id: "price",
    label: "Price",
    width: "minmax(80px,1fr)",
    defaultVisible: true,
    sortable: true,
    sortKey: (r) => r.price?.chaos_equiv ?? -1,
    display: (r) => {
      if (!r.price) return "—";
      if (r.currencyChaos) return formatChaosAsDivExLine(r.price.chaos_equiv, r.currencyChaos);
      return `${formatChaos(r.price.chaos_equiv)}c`;
    },
  },
  {
    id: "mods",
    label: "Mods",
    width: "1fr",
    defaultVisible: true,
    sortable: false,
    display: (r) => r.item.explicit_mods.slice(0, 2).join(" · "),
  },
  {
    id: "rarity",
    label: "Rarity",
    width: "90px",
    defaultVisible: false,
    sortable: true,
    sortKey: (r) => r.item.rarity,
    display: (r) => r.item.rarity,
  },
  {
    id: "category",
    label: "Category",
    width: "90px",
    defaultVisible: false,
    sortable: true,
    sortKey: (r) => r.category,
    display: (r) => r.category,
  },
  {
    id: "sockets",
    label: "Sockets",
    width: "70px",
    defaultVisible: false,
    sortable: true,
    sortKey: (r) => r.item.sockets.length,
    display: (r) => {
      const count = r.item.sockets.length;
      if (count === 0) return "—";
      const types = [...new Set(r.item.sockets.map((s) => s.type))];
      const label = types.length === 1 ? types[0] : "mixed";
      return `${count} ${label}`;
    },
  },
  {
    id: "corrupted",
    label: "Corrupted",
    width: "80px",
    defaultVisible: false,
    sortable: true,
    sortKey: (r) => (r.item.corrupted ? 1 : 0),
    display: (r) => (r.item.double_corrupted ? "2×" : r.item.corrupted ? "yes" : "—"),
  },
  {
    id: "identified",
    label: "Identified",
    width: "80px",
    defaultVisible: false,
    sortable: true,
    sortKey: (r) => (r.item.identified ? 1 : 0),
    display: (r) => (r.item.identified ? "yes" : "no"),
  },
  {
    id: "implicits",
    label: "Implicits",
    width: "minmax(100px,1fr)",
    defaultVisible: false,
    sortable: false,
    display: (r) => r.item.implicit_mods.slice(0, 2).join(" · "),
  },
  {
    id: "runeforged",
    label: "Runeforged",
    width: "90px",
    defaultVisible: false,
    sortable: true,
    sortKey: (r) => (r.item.runeforged ? 1 : 0),
    display: (r) => (r.item.runeforged ? "yes" : "—"),
  },
];

export const COLUMN_BY_ID: Readonly<Record<ColumnId, ColumnDef>> = Object.fromEntries(
  ALL_COLUMNS.map((c) => [c.id, c]),
) as Record<ColumnId, ColumnDef>;

export const DEFAULT_VISIBLE_COLUMN_IDS: readonly ColumnId[] = ALL_COLUMNS.filter(
  (c) => c.defaultVisible,
).map((c) => c.id);

export function compareRows(a: TableRow, b: TableRow, colId: ColumnId, dir: SortDirection): number {
  const col = COLUMN_BY_ID[colId];
  if (!col.sortKey) return 0;
  const ka = col.sortKey(a);
  const kb = col.sortKey(b);
  let cmp = 0;
  if (typeof ka === "number" && typeof kb === "number") {
    cmp = ka - kb;
  } else {
    cmp = String(ka).localeCompare(String(kb));
  }
  return dir === "asc" ? cmp : -cmp;
}
