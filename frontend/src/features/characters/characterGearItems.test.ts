import { describe, expect, it } from "vitest";

import type { CharacterDetail, Item } from "@/api/types";
import {
  collectCharacterGearPricingItems,
  computeGearEstimate,
} from "./characterGearItems";

function item(id: string, slot: string | null = null): Item {
  return {
    id,
    inventory_id: slot,
    w: 1,
    h: 1,
    x: null,
    y: null,
    name: id,
    type_line: id,
    base_type: id,
    rarity: "Rare",
    ilvl: 80,
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
  };
}

describe("collectCharacterGearPricingItems", () => {
  it("includes paper-doll items, jewels, and notable gems without duplicates", () => {
    const detail: Pick<CharacterDetail, "equipped" | "gems" | "jewels" | "inventory"> = {
      equipped: [item("helm", "Helm"), item("body", "BodyArmour")],
      gems: [{ ...item("gem1", "SkillSlots"), rarity: "Gem" as const, type_line: "Fireball" }],
      jewels: [item("jewel1", "PassiveJewels")],
      inventory: [],
    };
    const ids = collectCharacterGearPricingItems(detail).map((i) => i.id);
    expect(ids).toEqual(expect.arrayContaining(["helm", "body", "gem1", "jewel1"]));
    expect(ids).toHaveLength(4);
  });

  it("dedupes when the same item appears in multiple buckets", () => {
    const shared = item("ring", "Ring");
    const detail: Pick<CharacterDetail, "equipped" | "gems" | "jewels" | "inventory"> = {
      equipped: [shared],
      gems: [],
      jewels: [],
      inventory: [shared],
    };
    expect(collectCharacterGearPricingItems(detail)).toHaveLength(1);
  });
});

describe("computeGearEstimate", () => {
  it("sums priced items and counts coverage", () => {
    const items = [item("a"), item("b"), item("c")];
    const result = computeGearEstimate(items, {
      a: { chaos_equiv: 10, value: 10, unit: "chaos", source: "static", confidence: 1, note: null },
      c: { chaos_equiv: 5, value: 5, unit: "chaos", source: "static", confidence: 1, note: null },
    });
    expect(result).toEqual({ totalChaos: 15, pricedCount: 2, totalCount: 3 });
  });
});
