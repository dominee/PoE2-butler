import { describe, expect, it } from "vitest";

import type { Item } from "@/api/types";
import {
  collectCharacterOtherInventory,
  collectCharacterSkillGemsForDisplay,
  collectCharacterSupportGemsForDisplay,
  filterCharacterGemsForPricing,
  filterNotableCharacterGems,
  isCharacterSkillGem,
  isDisplayedInSkillGemsSection,
  isDisplayedInSupportGemsSection,
  isLineageSupportGem,
  isNotableCharacterGem,
  shouldIncludeCharacterGemInPricing,
} from "./characterGemFilter";

function gem(partial: Partial<Item> & Pick<Item, "id" | "type_line">): Item {
  return {
    inventory_id: "SkillSlots",
    w: 1,
    h: 1,
    x: null,
    y: null,
    name: "",
    base_type: partial.type_line,
    rarity: "Gem",
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
    ...partial,
  };
}

describe("isCharacterSkillGem / display sections", () => {
  it("hides tiered generic supports like Brutality I", () => {
    const item = gem({
      id: "1",
      type_line: "Brutality I",
      properties: [{ name: "[SupportGem|Support], [Physical]", value: null }],
    });
    expect(isCharacterSkillGem(item)).toBe(false);
    expect(isDisplayedInSkillGemsSection(item)).toBe(false);
    expect(isDisplayedInSupportGemsSection(item)).toBe(false);
  });

  it("shows Lineage supports in support section only", () => {
    const item = gem({
      id: "2",
      type_line: "Rakiata's Flow",
      properties: [{ name: "[SupportGem|Support], [LineageSupports|Lineage]", value: null }],
    });
    expect(isLineageSupportGem(item)).toBe(true);
    expect(isCharacterSkillGem(item)).toBe(false);
    expect(isDisplayedInSkillGemsSection(item)).toBe(false);
    expect(isDisplayedInSupportGemsSection(item)).toBe(true);
  });

  it("shows active skill gems in skill section only", () => {
    const item = gem({
      id: "3",
      type_line: "Ice Nova",
      properties: [{ name: "Spell, AoE, Cold", value: null }],
    });
    expect(isCharacterSkillGem(item)).toBe(true);
    expect(isDisplayedInSkillGemsSection(item)).toBe(true);
    expect(isDisplayedInSupportGemsSection(item)).toBe(false);
  });

  it("shows ascendancy skills in skill section", () => {
    const item = gem({
      id: "4",
      type_line: "Ascendancy Skill",
      inventory_id: "AscendancySkills",
    });
    expect(isCharacterSkillGem(item)).toBe(true);
    expect(isDisplayedInSkillGemsSection(item)).toBe(true);
  });

  it("shows item-granted skills in skill section", () => {
    const item = gem({
      id: "5",
      type_line: "Molten Shower",
      inventory_id: null,
      properties: [{ name: "Spell, Fire", value: null }],
    });
    expect(isCharacterSkillGem(item)).toBe(true);
    expect(isDisplayedInSkillGemsSection(item)).toBe(true);
  });
});

describe("shouldIncludeCharacterGemInPricing", () => {
  it("includes only Lineage supports", () => {
    const lineage = gem({
      id: "b",
      type_line: "Rakiata's Flow",
      properties: [{ name: "Support, Lineage", value: null }],
    });
    const skill = gem({
      id: "a",
      type_line: "Ice Nova",
      properties: [{ name: "Spell, Cold", value: null }],
    });
    expect(shouldIncludeCharacterGemInPricing(lineage)).toBe(true);
    expect(shouldIncludeCharacterGemInPricing(skill)).toBe(false);
  });
});

describe("filterNotableCharacterGems / filterCharacterGemsForPricing", () => {
  it("filters display vs pricing lists differently", () => {
    const gems = [
      gem({ id: "a", type_line: "Brutality I", properties: [{ name: "Support, Physical", value: null }] }),
      gem({ id: "b", type_line: "Rakiata's Flow", properties: [{ name: "Support, Lineage", value: null }] }),
      gem({ id: "c", type_line: "Ice Nova", properties: [{ name: "Spell, Cold", value: null }] }),
    ];
    expect(filterNotableCharacterGems(gems).map((g) => g.id)).toEqual(["b", "c"]);
    expect(filterCharacterGemsForPricing(gems).map((g) => g.id)).toEqual(["b"]);
  });
});

describe("isNotableCharacterGem", () => {
  it("includes both skill and support display sections", () => {
    const skill = gem({ id: "3", type_line: "Ice Nova" });
    const lineage = gem({
      id: "2",
      type_line: "Rakiata's Flow",
      properties: [{ name: "Support, Lineage", value: null }],
    });
    expect(isNotableCharacterGem(skill)).toBe(true);
    expect(isNotableCharacterGem(lineage)).toBe(true);
  });
});

describe("collectCharacterSkillGemsForDisplay", () => {
  it("merges gems and inventory item-granted skills, excluding lineage", () => {
    const skillInGems = gem({ id: "g1", type_line: "Fireball" });
    const grantedInInventory = gem({
      id: "inv1",
      type_line: "Purity of Ice",
      inventory_id: null,
    });
    const lineage = gem({
      id: "lin1",
      type_line: "Rakiata's Flow",
      properties: [{ name: "Support, Lineage", value: null }],
    });
    const detail = {
      gems: [skillInGems, lineage],
      inventory: [
        grantedInInventory,
        gem({ id: "brut", type_line: "Brutality I", properties: [{ name: "Support", value: null }] }),
      ],
    };
    expect(collectCharacterSkillGemsForDisplay(detail).map((g) => g.id)).toEqual(["g1", "inv1"]);
  });
});

describe("collectCharacterSupportGemsForDisplay", () => {
  it("collects lineage supports from gems and inventory", () => {
    const lineage = gem({
      id: "lin1",
      type_line: "Rakiata's Flow",
      properties: [{ name: "Support, Lineage", value: null }],
    });
    const skill = gem({ id: "g1", type_line: "Fireball" });
    const detail = { gems: [skill, lineage], inventory: [] };
    expect(collectCharacterSupportGemsForDisplay(detail).map((g) => g.id)).toEqual(["lin1"]);
  });
});

describe("collectCharacterOtherInventory", () => {
  it("excludes skill and support gems shown in their sections", () => {
    const granted = gem({ id: "inv1", type_line: "Molten Shower", inventory_id: null });
    const lineage = gem({
      id: "lin1",
      type_line: "Rakiata's Flow",
      properties: [{ name: "Support, Lineage", value: null }],
    });
    const flask = { ...gem({ id: "f1", type_line: "Flask" }), rarity: "Unique" as const, inventory_id: "Flask" };
    const detail = { gems: [lineage], inventory: [granted, flask] };
    expect(collectCharacterOtherInventory(detail).map((i) => i.id)).toEqual(["f1"]);
  });
});

describe("nested socketed_items (Her Declaration bug)", () => {
  it("finds a lineage gem in skill.socketed_items via collectCharacterSupportGemsForDisplay", () => {
    const lineage = gem({
      id: "her-declaration",
      type_line: "Her Declaration",
      inventory_id: null,
      properties: [{ name: "[SupportGem|Support], [LineageSupports|Lineage]", value: null }],
    });
    const skill = gem({
      id: "purity-of-ice",
      type_line: "Purity of Ice",
      properties: [{ name: "Spell, AoE, Cold", value: null }],
      socketed_items: [lineage],
    });
    const detail = { gems: [skill], inventory: [] };
    const found = collectCharacterSupportGemsForDisplay(detail).map((g) => g.id);
    expect(found).toContain("her-declaration");
    expect(found).not.toContain("purity-of-ice");
  });

  it("does not surface generic supports nested in skill socketed_items", () => {
    const genericSupport = gem({
      id: "magnified-area",
      type_line: "Magnified Area II",
      inventory_id: null,
      properties: [{ name: "[SupportGem|Support], [AoESkill|AoE]", value: null }],
    });
    const skill = gem({
      id: "lightning-bolt",
      type_line: "Lightning Bolt",
      properties: [{ name: "Spell, Lightning", value: null }],
      socketed_items: [genericSupport],
    });
    const detail = { gems: [skill], inventory: [] };
    const skills = collectCharacterSkillGemsForDisplay(detail).map((g) => g.id);
    const supports = collectCharacterSupportGemsForDisplay(detail).map((g) => g.id);
    expect(skills).toContain("lightning-bolt");
    expect(supports).not.toContain("magnified-area");
  });

  it("deduplicates when lineage appears both in inventory and skill.socketed_items", () => {
    const lineage = gem({
      id: "her-declaration",
      type_line: "Her Declaration",
      inventory_id: null,
      properties: [{ name: "Support, Lineage", value: null }],
    });
    const skill = gem({
      id: "skill1",
      type_line: "Fireball",
      socketed_items: [lineage],
    });
    const detail = { gems: [skill], inventory: [lineage] };
    const found = collectCharacterSupportGemsForDisplay(detail);
    expect(found.filter((g) => g.id === "her-declaration")).toHaveLength(1);
  });
});
