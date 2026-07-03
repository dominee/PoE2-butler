import { describe, expect, it, vi } from "vitest";

import { itemIconDisplayUrl, itemIconForExportPng, itemRarityFaviconPath } from "./itemRarityFavicon";
import type { Item } from "@/api/types";

const baseItem: Item = {
  id: "i1",
  inventory_id: null,
  w: 1,
  h: 1,
  x: null,
  y: null,
  name: "",
  type_line: "Test",
  base_type: "Test",
  rarity: "Normal",
  ilvl: null,
  identified: true,
  corrupted: false,
  properties: [],
  requirements: [],
  implicit_mods: [],
  implicit_mod_details: [],
  explicit_mods: [],
  explicit_mod_details: [],
  socketed_items: [],
  rune_mods: [],
  enchant_mods: [],
  crafted_mods: [],
  sockets: [],
  stack_size: null,
  max_stack_size: null,
  icon: null,
  implicit_mod_range_hints: [],
  explicit_mod_range_hints: [],
};

describe("itemRarityFaviconPath", () => {
  it("maps each ItemRarity to a same-origin path", () => {
    expect(itemRarityFaviconPath("Normal")).toBe("/icons/item-rarity/normal.svg");
    expect(itemRarityFaviconPath("DivinationCard")).toBe("/icons/item-rarity/divination.svg");
  });
});

describe("itemIconDisplayUrl", () => {
  it("uses GGG art when item.icon is set", () => {
    const url = "https://other.example.com/x.png";
    expect(itemIconDisplayUrl({ ...baseItem, icon: url, rarity: "Normal" })).toBe(url);
  });

  it("uses a rarity placeholder when item.icon is missing", () => {
    expect(
      itemIconDisplayUrl({ ...baseItem, icon: null, rarity: "Unique" }),
    ).toBe("/icons/item-rarity/unique.svg");
  });
});

describe("itemIconForExportPng", () => {
  it("uses proxy for web.poecdn.com icons in export context", () => {
    const u = "https://web.poecdn.com/gen/image/abc/1/Foo.png";
    const item = { ...baseItem, icon: u, rarity: "Normal" as const };
    expect(itemIconForExportPng(item)).toContain(
      `/api/cdn/poecdn?u=${encodeURIComponent(u)}`,
    );
  });

  it("uses absolute proxy URLs in the browser for off-screen export", () => {
    const u = "https://web.poecdn.com/gen/image/abc/1/Foo.png";
    const item = { ...baseItem, icon: u, rarity: "Normal" as const };
    vi.stubGlobal("window", { location: { origin: "https://app.example.test" } });
    expect(itemIconForExportPng(item)).toBe(
      `https://app.example.test/api/cdn/poecdn?u=${encodeURIComponent(u)}`,
    );
    vi.unstubAllGlobals();
  });

  it("uses rarity path when there is no icon", () => {
    expect(
      itemIconForExportPng({ ...baseItem, icon: null, rarity: "Currency" }),
    ).toContain("/icons/item-rarity/currency.svg");
  });
});
