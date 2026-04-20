import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { Item } from "@/api/types";
import { ItemCard } from "./ItemCard";

const baseItem: Item = {
  id: "i1",
  inventory_id: "Weapon",
  w: 2,
  h: 4,
  x: null,
  y: null,
  name: "Doom Horn",
  type_line: "Spine Bow",
  base_type: "Spine Bow",
  rarity: "Rare",
  ilvl: 82,
  identified: true,
  corrupted: false,
  properties: [],
  requirements: [],
  implicit_mods: [],
  explicit_mods: ["+45 to maximum Life", "60% increased Physical Damage"],
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

describe("ItemCard", () => {
  it("renders name, type_line and first few mods", () => {
    render(<ItemCard item={baseItem} />);
    expect(screen.getByText(/doom horn/i)).toBeInTheDocument();
    expect(screen.getByText(/spine bow/i)).toBeInTheDocument();
    expect(screen.getByText(/\+45 to maximum life/i)).toBeInTheDocument();
    expect(screen.getByText(/ilvl 82/i)).toBeInTheDocument();
  });

  it("shows corruption flag when corrupted", () => {
    render(<ItemCard item={{ ...baseItem, corrupted: true }} />);
    expect(screen.getByText(/corrupted/i)).toBeInTheDocument();
  });

  it("fires onClick with the item", async () => {
    const user = userEvent.setup();
    const handle = vi.fn();
    render(<ItemCard item={baseItem} onClick={handle} />);
    await user.click(screen.getByTestId("item-card"));
    expect(handle).toHaveBeenCalledWith(baseItem);
  });
});
