import { describe, expect, it } from "vitest";

import { ALL_COLUMNS, COLUMN_BY_ID, DEFAULT_VISIBLE_COLUMN_IDS, compareRows } from "./characterTableColumns";
import type { TableRow } from "./characterTableColumns";
import type { Item } from "@/api/types";

function makeRow(overrides: Partial<Item> = {}, priceEquiv?: number): TableRow {
  const item: Item = {
    id: "i1",
    inventory_id: "Helm",
    w: 2,
    h: 2,
    x: null,
    y: null,
    name: "Test Helm",
    type_line: "Iron Hat",
    base_type: "Iron Hat",
    rarity: "Rare",
    ilvl: 80,
    identified: true,
    corrupted: false,
    properties: [],
    requirements: [],
    implicit_mods: ["Adds 10 to 20 Physical Damage"],
    implicit_mod_details: [],
    explicit_mods: ["+100 to maximum Life", "+40 to Strength"],
    explicit_mod_details: [],
    socketed_items: [],
    rune_mods: [],
    enchant_mods: [],
    crafted_mods: [],
    sockets: [{ group: 0, type: "rune" }],
    stack_size: null,
    max_stack_size: null,
    icon: null,
    ...overrides,
  };
  return {
    item,
    category: "equipped",
    price: priceEquiv != null
      ? { chaos_equiv: priceEquiv, value: priceEquiv, unit: "chaos", source: "static", confidence: 1, note: null }
      : null,
    slotLabel: item.inventory_id ?? "—",
    currencyChaos: null,
  };
}

describe("ALL_COLUMNS registry", () => {
  it("has exactly 13 columns", () => {
    expect(ALL_COLUMNS).toHaveLength(13);
  });

  it("default visible columns are slot, name, base_type, ilvl, price, mods", () => {
    expect(DEFAULT_VISIBLE_COLUMN_IDS).toEqual(["slot", "name", "base_type", "ilvl", "price", "mods"]);
  });

  it("all column ids are unique", () => {
    const ids = ALL_COLUMNS.map((c) => c.id);
    expect(new Set(ids).size).toBe(ids.length);
  });

  it("COLUMN_BY_ID contains every column", () => {
    for (const col of ALL_COLUMNS) {
      expect(COLUMN_BY_ID[col.id]).toBe(col);
    }
  });
});

describe("column display functions", () => {
  it("slot column displays slotLabel", () => {
    const row = makeRow();
    row.slotLabel = "Body armour";
    expect(COLUMN_BY_ID.slot.display(row)).toBe("Body armour");
  });

  it("ilvl column displays item level or — for null", () => {
    expect(COLUMN_BY_ID.ilvl.display(makeRow({ ilvl: 82 }))).toBe("82");
    expect(COLUMN_BY_ID.ilvl.display(makeRow({ ilvl: null }))).toBe("—");
  });

  it("sockets column describes type for single-type sockets", () => {
    const row = makeRow({ sockets: [{ group: 0, type: "rune" }, { group: 1, type: "rune" }] });
    expect(COLUMN_BY_ID.sockets.display(row)).toBe("2 rune");
  });

  it("sockets column shows — for no sockets", () => {
    const row = makeRow({ sockets: [] });
    expect(COLUMN_BY_ID.sockets.display(row)).toBe("—");
  });

  it("corrupted column shows 2× for double-corrupted", () => {
    const row = makeRow({ corrupted: true, double_corrupted: true });
    expect(COLUMN_BY_ID.corrupted.display(row)).toBe("2×");
  });

  it("corrupted column shows yes for single-corrupted", () => {
    const row = makeRow({ corrupted: true });
    expect(COLUMN_BY_ID.corrupted.display(row)).toBe("yes");
  });

  it("corrupted column shows — for clean items", () => {
    expect(COLUMN_BY_ID.corrupted.display(makeRow())).toBe("—");
  });

  it("implicits column shows first two implicit mods joined with ·", () => {
    const row = makeRow();
    expect(COLUMN_BY_ID.implicits.display(row)).toContain("Adds 10 to 20 Physical Damage");
  });
});

describe("sortable columns", () => {
  it("price sorts by chaos_equiv", () => {
    const cheap = makeRow({}, 10);
    const expensive = makeRow({}, 100);
    expect(compareRows(cheap, expensive, "price", "asc")).toBeLessThan(0);
    expect(compareRows(cheap, expensive, "price", "desc")).toBeGreaterThan(0);
  });

  it("mods column is not sortable", () => {
    expect(COLUMN_BY_ID.mods.sortable).toBe(false);
    expect(COLUMN_BY_ID.mods.sortKey).toBeUndefined();
  });

  it("implicits column is not sortable", () => {
    expect(COLUMN_BY_ID.implicits.sortable).toBe(false);
  });
});
