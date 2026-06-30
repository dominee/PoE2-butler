import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { CharacterSnapshotTimeline } from "./CharacterSnapshotTimeline";

const mockUseCharacterSnapshots = vi.fn();

vi.mock("@/api/hooks", () => ({
  useCharacterSnapshots: (...args: unknown[]) => mockUseCharacterSnapshots(...args),
}));

describe("CharacterSnapshotTimeline", () => {
  it("renders dots and calls onSelect when a historic dot is clicked", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    mockUseCharacterSnapshots.mockReturnValue({
      isSuccess: true,
      data: {
        character_name: "Hero",
        snapshots: [
          {
            id: 1,
            fetched_at: "2026-06-01T12:00:00Z",
            is_current: false,
          },
          {
            id: null,
            fetched_at: "2026-06-03T12:00:00Z",
            is_current: true,
          },
        ],
      },
    });

    render(
      <CharacterSnapshotTimeline
        characterName="Hero"
        selectedId="current"
        onSelect={onSelect}
      />,
    );

    expect(screen.getByTestId("character-snapshot-timeline")).toBeInTheDocument();
    expect(screen.getByTestId("snapshot-dot-1")).toBeInTheDocument();
    expect(screen.getByTestId("snapshot-dot-current")).toBeInTheDocument();

    await user.click(screen.getByTestId("snapshot-dot-1"));
    expect(onSelect).toHaveBeenCalledWith(1);
  });

  it("hides when no snapshots are available", () => {
    mockUseCharacterSnapshots.mockReturnValue({
      isSuccess: true,
      data: { character_name: "Hero", snapshots: [] },
    });

    render(
      <CharacterSnapshotTimeline
        characterName="Hero"
        selectedId="current"
        onSelect={vi.fn()}
      />,
    );

    expect(screen.queryByTestId("character-snapshot-timeline")).not.toBeInTheDocument();
  });
});
