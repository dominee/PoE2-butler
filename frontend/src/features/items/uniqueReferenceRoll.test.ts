import { describe, expect, it } from "vitest";

import {
  itemReferenceRollPcts,
  parseTypeRangeFromHint,
  uniqueTypeRollPercent,
} from "./uniqueReferenceRoll";

import type { Item, ItemRarity } from "@/api/types";

function _item(over: Partial<Item>): Item {
  return {
    id: "x",
    inventory_id: null,
    w: 1,
    h: 1,
    x: null,
    y: null,
    name: "U",
    type_line: "Belt",
    base_type: "Belt",
    rarity: "Unique" as ItemRarity,
    ilvl: 80,
    identified: true,
    corrupted: false,
    properties: [],
    requirements: [],
    implicit_mods: [],
    implicit_mod_details: [],
    explicit_mods: [],
    explicit_mod_details: [],
    rune_mods: [],
    enchant_mods: [],
    crafted_mods: [],
    sockets: [],
    socketed_items: [],
    stack_size: null,
    max_stack_size: null,
    icon: null,
    ...over,
  };
}

describe("parseTypeRangeFromHint", () => {
  it("parses +life, paren% and slots", () => {
    expect(parseTypeRangeFromHint("+(40—60)")).toEqual({ min: 40, max: 60 });
    expect(parseTypeRangeFromHint("+(20—30)%")).toEqual({ min: 20, max: 30 });
    expect(parseTypeRangeFromHint("(20—30)%")).toEqual({ min: 20, max: 30 });
    expect(parseTypeRangeFromHint("(1—3) Slots")).toEqual({ min: 1, max: 3 });
  });
});

describe("uniqueTypeRollPercent", () => {
  it("interpolates life and charm slots toward max", () => {
    expect(uniqueTypeRollPercent("+53 to maximum Life", "+(40—60)")).toBe(65);
    expect(uniqueTypeRollPercent("Has 1 Charm Slot", "(1—3) Slots")).toBe(0);
    expect(uniqueTypeRollPercent("Has 3 Charm Slots", "(1—3) Slots")).toBe(100);
  });

  it("treats reduced% as better when lower", () => {
    expect(
      uniqueTypeRollPercent("16% reduced [Attack] Speed", "(15—20)%"),
    ).toBe(80);
  });
});

describe("itemReferenceRollPcts", () => {
  it("zips implicits then explicits", () => {
    const p = _item({
      implicit_mods: ['26% increased [StunThreshold|Stun Threshold]'],
      implicit_mod_range_hints: ["(20—30)%"],
      explicit_mods: ["+41 to maximum Life", "noop"],
      explicit_mod_range_hints: ["+(40—60)", null],
    });
    const a = itemReferenceRollPcts(p);
    expect(a[0]).toBe(60);
    expect(a[1]).toBe(5);
    expect(a[2]).toBeNull();
  });
});
