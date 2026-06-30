import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { CharacterSnapshotTimeline } from "./CharacterSnapshotTimeline";

const mockUseCharacterSnapshots = vi.fn();

vi.mock("@/api/hooks", () => ({
  useCharacterSnapshots: (...args: unknown[]) => mockUseCharacterSnapshots(...args),
}));

describe("CharacterSnapshotTimeline", () => {
  it("renders datetime, change list, and calls onSelect when a dot is clicked", async () => {
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
            changes: [{ kind: "changed", label: "Test Chest" }],
          },
          {
            id: 2,
            fetched_at: "2026-06-03T12:00:00Z",
            is_current: true,
            changes: [{ kind: "new", label: "Gold Ring" }],
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
    expect(screen.getByTestId("snapshot-change-list")).toHaveTextContent("+ Gold Ring");

    await user.click(screen.getByTestId("snapshot-dot-1"));
    expect(onSelect).toHaveBeenCalledWith(1);
  });

  it("shows change list for selected historic dot", async () => {
    const user = userEvent.setup();
    mockUseCharacterSnapshots.mockReturnValue({
      isSuccess: true,
      data: {
        character_name: "Hero",
        snapshots: [
          {
            id: 1,
            fetched_at: "2026-06-01T12:00:00Z",
            is_current: false,
            changes: [{ kind: "changed", label: "Test Chest" }],
          },
          {
            id: 2,
            fetched_at: "2026-06-03T12:00:00Z",
            is_current: true,
            changes: [{ kind: "new", label: "Gold Ring" }],
          },
        ],
      },
    });

    render(
      <CharacterSnapshotTimeline
        characterName="Hero"
        selectedId={1}
        onSelect={vi.fn()}
      />,
    );

    const list = screen.getByTestId("snapshot-change-list");
    expect(within(list).getByText(/Test Chest/)).toBeInTheDocument();

    await user.click(screen.getByTestId("snapshot-dot-current"));
  });

  it("stays visible with a current-only dot when no change history exists", () => {
    mockUseCharacterSnapshots.mockReturnValue({
      isSuccess: true,
      isLoading: false,
      data: {
        character_name: "Hero",
        snapshots: [
          {
            id: null,
            fetched_at: "2026-06-03T12:00:00Z",
            is_current: true,
            changes: [],
          },
        ],
      },
    });

    render(
      <CharacterSnapshotTimeline
        characterName="Hero"
        selectedId="current"
        onSelect={vi.fn()}
      />,
    );

    expect(screen.getByTestId("character-snapshot-timeline")).toBeInTheDocument();
    expect(screen.getByTestId("snapshot-dot-current")).toBeInTheDocument();
    expect(screen.getByTestId("snapshot-current-hint")).toBeInTheDocument();
  });

  it("stays visible while loading and shows a loading message", () => {
    mockUseCharacterSnapshots.mockReturnValue({
      isSuccess: false,
      isLoading: true,
      data: undefined,
    });

    render(
      <CharacterSnapshotTimeline
        characterName="Hero"
        selectedId="current"
        onSelect={vi.fn()}
      />,
    );

    expect(screen.getByTestId("character-snapshot-timeline")).toBeInTheDocument();
    expect(screen.getByText(/Loading snapshot timeline/)).toBeInTheDocument();
  });

  it("stays visible with an empty hint when loaded but no snapshots exist", () => {
    mockUseCharacterSnapshots.mockReturnValue({
      isSuccess: true,
      isLoading: false,
      data: { character_name: "Hero", snapshots: [] },
    });

    render(
      <CharacterSnapshotTimeline
        characterName="Hero"
        selectedId="current"
        onSelect={vi.fn()}
      />,
    );

    expect(screen.getByTestId("character-snapshot-timeline")).toBeInTheDocument();
    expect(screen.getByText(/No snapshots yet/)).toBeInTheDocument();
  });
});
