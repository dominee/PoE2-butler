import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { PublicCharacterPage } from "./PublicCharacterPage";

const mockUsePublicCharacter = vi.fn();

vi.mock("@/api/hooks", () => ({
  usePublicCharacter: (...args: unknown[]) => mockUsePublicCharacter(...args),
}));

const routerFuture = {
  v7_startTransition: true,
  v7_relativeSplatPath: true,
} as const;

describe("PublicCharacterPage", () => {
  it("renders simple character gear view", () => {
    mockUsePublicCharacter.mockReturnValue({
      isLoading: false,
      isError: false,
      data: {
        league: "Standard",
        character_name: "Hero",
        view_mode: "simple",
        character: {
          summary: {
            id: "1",
            name: "Hero",
            realm: "poe2",
            class: "Ranger",
            level: 90,
            league: "Standard",
            experience: 1000,
          },
          equipped: [
            {
              id: "body1",
              inventory_id: "BodyArmour",
              w: 2,
              h: 3,
              x: null,
              y: null,
              name: "Test Chest",
              type_line: "Leather Vest",
              base_type: "Leather Vest",
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
            },
          ],
          gems: [],
          jewels: [],
          inventory: [],
        },
      },
    });

    render(
      <MemoryRouter future={routerFuture} initialEntries={["/c/abc"]}>
        <Routes>
          <Route path="/c/:shareId" element={<PublicCharacterPage />} />
        </Routes>
      </MemoryRouter>,
    );

    expect(screen.getByText("Hero")).toBeInTheDocument();
    expect(screen.getByText(/Lv 90/)).toBeInTheDocument();
    expect(screen.getByText("Test Chest")).toBeInTheDocument();
  });

  it("renders detailed view test id when view_mode is detailed", () => {
    mockUsePublicCharacter.mockReturnValue({
      isLoading: false,
      isError: false,
      data: {
        league: "Standard",
        character_name: "Hero",
        view_mode: "detailed",
        character: {
          summary: {
            id: "1",
            name: "Hero",
            realm: "poe2",
            class: "Ranger",
            level: 90,
            league: "Standard",
            experience: 1000,
          },
          equipped: [
            {
              id: "body1",
              inventory_id: "BodyArmour",
              w: 2,
              h: 3,
              x: null,
              y: null,
              name: "Test Chest",
              type_line: "Leather Vest",
              base_type: "Leather Vest",
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
            },
          ],
          gems: [],
          jewels: [],
          inventory: [],
        },
      },
    });

    render(
      <MemoryRouter future={routerFuture} initialEntries={["/c/abc"]}>
        <Routes>
          <Route path="/c/:shareId" element={<PublicCharacterPage />} />
        </Routes>
      </MemoryRouter>,
    );

    expect(screen.getByTestId("character-detailed-gear")).toBeInTheDocument();
  });
});
