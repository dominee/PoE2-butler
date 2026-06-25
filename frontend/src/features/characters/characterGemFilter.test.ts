import { describe, expect, it } from "vitest";

import type { Item } from "@/api/types";
import { filterNotableCharacterGems, isNotableCharacterGem } from "./characterGemFilter";

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

describe("isNotableCharacterGem", () => {
  it("hides tiered generic supports like Brutality I", () => {
    const item = gem({
      id: "1",
      type_line: "Brutality I",
      properties: [{ name: "[SupportGem|Support], [Physical]", value: null }],
    });
    expect(isNotableCharacterGem(item)).toBe(false);
  });

  it("shows Lineage supports like Rakiata's Flow", () => {
    const item = gem({
      id: "2",
      type_line: "Rakiata's Flow",
      properties: [{ name: "[SupportGem|Support], [LineageSupports|Lineage]", value: null }],
    });
    expect(isNotableCharacterGem(item)).toBe(true);
  });

  it("shows active skill gems", () => {
    const item = gem({
      id: "3",
      type_line: "Ice Nova",
      properties: [{ name: "Spell, AoE, Cold", value: null }],
    });
    expect(isNotableCharacterGem(item)).toBe(true);
  });
});

describe("filterNotableCharacterGems", () => {
  it("filters a mixed list", () => {
    const gems = [
      gem({ id: "a", type_line: "Brutality I", properties: [{ name: "Support, Physical", value: null }] }),
      gem({ id: "b", type_line: "Rakiata's Flow", properties: [{ name: "Support, Lineage", value: null }] }),
    ];
    expect(filterNotableCharacterGems(gems).map((g) => g.id)).toEqual(["b"]);
  });
});
