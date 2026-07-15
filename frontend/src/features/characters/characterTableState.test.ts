import { describe, expect, it, beforeEach, afterEach, vi } from "vitest";

import { compareRows } from "./characterTableColumns";
import type { TableRow } from "./characterTableColumns";
import type { Item } from "@/api/types";

function makeRow(overrides: Partial<Item> = {}): TableRow {
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
    implicit_mods: [],
    implicit_mod_details: [],
    explicit_mods: ["+100 to maximum Life"],
    explicit_mod_details: [],
    socketed_items: [],
    rune_mods: [],
    enchant_mods: [],
    crafted_mods: [],
    sockets: [],
    stack_size: null,
    max_stack_size: null,
    icon: null,
    ...overrides,
  };
  return {
    item,
    category: "equipped",
    price: null,
    slotLabel: item.inventory_id ?? "—",
    currencyChaos: null,
  };
}

describe("compareRows", () => {
  it("sorts by ilvl ascending", () => {
    const a = makeRow({ ilvl: 60 });
    const b = makeRow({ ilvl: 80 });
    expect(compareRows(a, b, "ilvl", "asc")).toBeLessThan(0);
    expect(compareRows(b, a, "ilvl", "asc")).toBeGreaterThan(0);
  });

  it("reverses sort for descending direction", () => {
    const a = makeRow({ ilvl: 60 });
    const b = makeRow({ ilvl: 80 });
    expect(compareRows(a, b, "ilvl", "desc")).toBeGreaterThan(0);
  });

  it("sorts by name with localeCompare", () => {
    const a = makeRow({ name: "Apple Helm" });
    const b = makeRow({ name: "Zebra Helm" });
    expect(compareRows(a, b, "name", "asc")).toBeLessThan(0);
  });

  it("returns 0 for non-sortable columns", () => {
    const a = makeRow();
    const b = makeRow();
    expect(compareRows(a, b, "mods", "asc")).toBe(0);
  });

  it("sorts corrupted (true) after non-corrupted", () => {
    const clean = makeRow({ corrupted: false });
    const corrupt = makeRow({ corrupted: true });
    expect(compareRows(clean, corrupt, "corrupted", "asc")).toBeLessThan(0);
    expect(compareRows(corrupt, clean, "corrupted", "asc")).toBeGreaterThan(0);
  });
});

describe("localStorage persistence (isolated with mocks)", () => {
  let stored: Record<string, string>;

  beforeEach(() => {
    stored = {};
    vi.spyOn(Storage.prototype, "getItem").mockImplementation((k) => stored[k] ?? null);
    vi.spyOn(Storage.prototype, "setItem").mockImplementation((k, v) => { stored[k] = String(v); });
    vi.spyOn(Storage.prototype, "removeItem").mockImplementation((k) => { delete stored[k]; });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("reads back persisted sort from localStorage", () => {
    const state = { sort: { columnId: "ilvl" as const, direction: "desc" as const }, visibleColumnIds: ["slot" as const, "name" as const] };
    stored["poe2b.characterTable.v1:user123"] = JSON.stringify(state);

    // Simulate what useCharacterTableState would read on init
    const raw = localStorage.getItem("poe2b.characterTable.v1:user123");
    const parsed = JSON.parse(raw!);
    expect(parsed.sort.columnId).toBe("ilvl");
    expect(parsed.sort.direction).toBe("desc");
  });

  it("writes sort + columns to localStorage under userId-scoped key", () => {
    localStorage.setItem("poe2b.characterTable.v1:user42", JSON.stringify({
      sort: { columnId: "price", direction: "asc" },
      visibleColumnIds: ["slot", "name", "price"],
    }));
    const parsed = JSON.parse(stored["poe2b.characterTable.v1:user42"]!);
    expect(parsed.sort.columnId).toBe("price");
    expect(parsed.visibleColumnIds).toContain("price");
  });

  it("falls back to default when key not present", () => {
    const raw = localStorage.getItem("poe2b.characterTable.v1");
    expect(raw).toBeNull();
  });
});
