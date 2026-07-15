import { describe, expect, it } from "vitest";

import type { CharacterDetail, Item } from "@/api/types";
import {
  collectCharacterGearPricingItems,
  computeGearEstimate,
  formatGearEstimateLabel,
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

function gem(id: string, typeLine: string, props: Item["properties"] = []): Item {
  return {
    ...item(id, "SkillSlots"),
    rarity: "Gem",
    type_line: typeLine,
    base_type: typeLine,
    properties: props,
  };
}

describe("collectCharacterGearPricingItems", () => {
  it("includes paper-doll items, jewels, and Lineage gems — not skill gems", () => {
    const detail: Pick<CharacterDetail, "equipped" | "gems" | "jewels" | "inventory"> = {
      equipped: [item("helm", "Helm"), item("body", "BodyArmour")],
      gems: [
        gem("skill1", "Fireball"),
        gem("lineage1", "Rakiata's Flow", [{ name: "Support, Lineage", value: null }]),
      ],
      jewels: [item("jewel1", "PassiveJewels")],
      inventory: [],
    };
    const ids = collectCharacterGearPricingItems(detail).map((i) => i.id);
    expect(ids).toEqual(expect.arrayContaining(["helm", "body", "lineage1", "jewel1"]));
    expect(ids).not.toContain("skill1");
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

  it("includes lineage gems nested inside a skill gem's socketed_items (Her Declaration bug)", () => {
    const lineage = gem("her-declaration", "Her Declaration", [
      { name: "Support, Lineage", value: null },
    ]);
    const skill = {
      ...gem("purity-of-ice", "Purity of Ice", [{ name: "Spell, AoE, Cold", value: null }]),
      socketed_items: [lineage],
    };
    const detail: Pick<CharacterDetail, "equipped" | "gems" | "jewels" | "inventory"> = {
      equipped: [],
      gems: [skill],
      jewels: [],
      inventory: [],
    };
    const ids = collectCharacterGearPricingItems(detail).map((i) => i.id);
    expect(ids).toContain("her-declaration");
    expect(ids).not.toContain("purity-of-ice");
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

describe("formatGearEstimateLabel", () => {
  it("formats div/ex total with item count in brackets", () => {
    const label = formatGearEstimateLabel(
      { totalChaos: 3600, pricedCount: 4, totalCount: 25 },
      { chaosPerDivine: 36, chaosPerExalted: 1 },
    );
    expect(label).toBe("100div (3600ex) [4/25 items]");
  });
});
