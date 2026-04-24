import { describe, expect, it } from "vitest";

import type { Item } from "@/api/types";
import { applyFilters } from "./filters";

function makeItem(partial: Partial<Item> = {}): Item {
  return {
    id: partial.id ?? "x",
    inventory_id: "Stash1",
    w: 1,
    h: 1,
    x: 0,
    y: 0,
    name: partial.name ?? "",
    type_line: partial.type_line ?? "",
    base_type: partial.base_type ?? "",
    rarity: partial.rarity ?? "Normal",
    ilvl: partial.ilvl ?? null,
    identified: partial.identified ?? true,
    corrupted: false,
    properties: [],
    requirements: [],
    implicit_mods: [],
    implicit_mod_details: [],
    explicit_mods: partial.explicit_mods ?? [],
    explicit_mod_details: [],
    rune_mods: [],
    enchant_mods: [],
    crafted_mods: [],
    sockets: [],
    socketed_items: [],
    stack_size: null,
    max_stack_size: null,
    icon: null,
  };
}

describe("applyFilters", () => {
  const items: Item[] = [
    makeItem({
      id: "a",
      name: "Brood Grip",
      type_line: "Iron Gauntlets",
      base_type: "Iron Gauntlets",
      rarity: "Rare",
      ilvl: 81,
      explicit_mods: ["+48 to maximum Life", "+22% Fire Resistance"],
    }),
    makeItem({
      id: "b",
      name: "",
      type_line: "Chaos Orb",
      base_type: "Chaos Orb",
      rarity: "Currency",
      ilvl: null,
      identified: true,
    }),
    makeItem({
      id: "c",
      name: "Doom Horn",
      type_line: "Spine Bow",
      base_type: "Spine Bow",
      rarity: "Magic",
      ilvl: 50,
      identified: false,
      explicit_mods: ["+100 to maximum Life"],
    }),
  ];

  it("returns everything when no filter is active", () => {
    const result = applyFilters(items, {
      q: "",
      rarity: "",
      minIlvl: null,
      identifiedOnly: false,
    });
    expect(result).toHaveLength(3);
  });

  it("filters by search across names, base types and mods", () => {
    const result = applyFilters(items, {
      q: "life",
      rarity: "",
      minIlvl: null,
      identifiedOnly: false,
    });
    expect(result.map((i) => i.id)).toEqual(["a", "c"]);
  });

  it("filters by rarity", () => {
    const result = applyFilters(items, {
      q: "",
      rarity: "Currency",
      minIlvl: null,
      identifiedOnly: false,
    });
    expect(result.map((i) => i.id)).toEqual(["b"]);
  });

  it("filters by min ilvl", () => {
    const result = applyFilters(items, {
      q: "",
      rarity: "",
      minIlvl: 70,
      identifiedOnly: false,
    });
    expect(result.map((i) => i.id)).toEqual(["a"]);
  });

  it("filters by identified only", () => {
    const result = applyFilters(items, {
      q: "",
      rarity: "",
      minIlvl: null,
      identifiedOnly: true,
    });
    expect(result.map((i) => i.id)).toEqual(["a", "b"]);
  });

  it("combines multiple filters", () => {
    const result = applyFilters(items, {
      q: "life",
      rarity: "Rare",
      minIlvl: 80,
      identifiedOnly: true,
    });
    expect(result.map((i) => i.id)).toEqual(["a"]);
  });
});
