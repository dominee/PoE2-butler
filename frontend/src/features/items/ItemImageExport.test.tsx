import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { ItemImageExportActions } from "./ItemImageExport";
import type { Item } from "@/api/types";

vi.mock("html-to-image", () => ({
  toPng: vi.fn().mockResolvedValue("data:image/png;base64,xx"),
}));

const minimalItem: Item = {
  id: "i1",
  inventory_id: null,
  w: 1,
  h: 1,
  x: 0,
  y: 0,
  name: "Test",
  type_line: "Base",
  base_type: "Base",
  rarity: "Rare",
  ilvl: 80,
  identified: true,
  corrupted: false,
  properties: [],
  requirements: [],
  implicit_mods: [],
  explicit_mods: ["+10 to maximum Life"],
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

describe("ItemImageExportActions", () => {
  it("renders export buttons", () => {
    render(<ItemImageExportActions item={minimalItem} />);
    expect(screen.getByRole("button", { name: /compact/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /detail/i })).toBeInTheDocument();
  });
});
