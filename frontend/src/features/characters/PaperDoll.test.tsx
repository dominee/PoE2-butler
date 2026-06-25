import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { Item } from "@/api/types";

import { PaperDoll } from "./PaperDoll";
import { collectPaperDollItems } from "./paperDollItems";

function gearItem(inventoryId: string, name: string): Item {
  return {
    id: inventoryId,
    inventory_id: inventoryId,
    w: 1,
    h: 1,
    x: null,
    y: null,
    name,
    type_line: name,
    base_type: name,
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

describe("PaperDoll", () => {
  it("renders armour slots alongside the main-hand weapon", () => {
    render(
      <PaperDoll
        equipped={[
          gearItem("Weapon", "Spine Bow"),
          gearItem("Helm", "Iron Hat"),
          gearItem("BodyArmour", "Leather Vest"),
          gearItem("Ring", "Gold Ring"),
        ]}
      />,
    );

    expect(screen.getByRole("button", { name: /item iron hat/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /item leather vest/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /item gold ring/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /item spine bow/i })).toBeInTheDocument();
  });
});

describe("collectPaperDollItems", () => {
  it("pulls mis-bucketed gear from inventory when slot ids are present", () => {
    const helm = gearItem("Helm", "Iron Hat");
    const items = collectPaperDollItems({
      equipped: [gearItem("Weapon", "Spine Bow")],
      gems: [],
      jewels: [],
      inventory: [helm],
    });

    expect(items.map((i) => i.inventory_id).sort()).toEqual(["Helm", "Weapon"]);
  });
});
