import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { CharacterListPanel } from "./CharacterListPanel";

const characters = [
  { id: "1", name: "Hero", realm: "poe2", class: "Warrior", level: 90, league: "Standard", experience: 1000 },
  { id: "2", name: "Mage", realm: "poe2", class: "Sorcerer", level: 85, league: "Standard", experience: 800 },
];

describe("CharacterListPanel", () => {
  it("shows character names when expanded and hides them when collapsed", async () => {
    const user = userEvent.setup();
    render(
      <CharacterListPanel
        characters={characters}
        isLoading={false}
        selected="Hero"
        onSelect={vi.fn()}
      />,
    );

    expect(screen.getByText("Hero")).toBeInTheDocument();
    expect(screen.getByText("Mage")).toBeInTheDocument();

    const toggle = screen.getByTitle("Collapse character list");
    expect(toggle).toHaveAttribute("aria-expanded", "true");

    await user.click(toggle);

    expect(screen.queryByText("Hero")).not.toBeInTheDocument();
    expect(screen.queryByText("Mage")).not.toBeInTheDocument();
    expect(screen.getByTitle("Expand character list")).toHaveAttribute("aria-expanded", "false");
  });

  it("shows character count badge when collapsed", async () => {
    const user = userEvent.setup();
    render(
      <CharacterListPanel
        characters={characters}
        isLoading={false}
        selected={null}
        onSelect={vi.fn()}
      />,
    );

    await user.click(screen.getByTitle("Collapse character list"));
    expect(screen.getByText("2")).toBeInTheDocument();
  });
});
