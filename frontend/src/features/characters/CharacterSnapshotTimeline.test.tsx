import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { CharacterSnapshotTimeline, snapshotChangeTier, snapshotDotColorClass } from "./CharacterSnapshotTimeline";

const mockUseCharacterSnapshots = vi.fn();

vi.mock("@/api/hooks", () => ({
  useCharacterSnapshots: (...args: unknown[]) => mockUseCharacterSnapshots(...args),
}));

describe("snapshotChangeTier / snapshotDotColorClass", () => {
  it("maps change counts to distinct tiers", () => {
    expect(snapshotChangeTier(0)).toBe("none");
    expect(snapshotChangeTier(1)).toBe("minimal");
    expect(snapshotChangeTier(2)).toBe("minimal");
    expect(snapshotChangeTier(3)).toBe("moderate");
    expect(snapshotChangeTier(5)).toBe("moderate");
    expect(snapshotChangeTier(6)).toBe("heavy");
    expect(snapshotChangeTier(10)).toBe("heavy");
    expect(snapshotChangeTier(11)).toBe("massive");
  });

  it("uses a different color class per tier", () => {
    const tiers = [0, 1, 4, 8, 12].map(snapshotDotColorClass);
    expect(new Set(tiers).size).toBe(5);
  });

  it("maps tiers to rarity and ember design tokens", () => {
    expect(snapshotDotColorClass(0)).toContain("ink-600");
    expect(snapshotDotColorClass(1)).toContain("rarity-magic");
    expect(snapshotDotColorClass(4)).toContain("rarity-rare");
    expect(snapshotDotColorClass(8)).toContain("rarity-unique");
    expect(snapshotDotColorClass(12)).toContain("ember-");
  });
});

describe("CharacterSnapshotTimeline", () => {
  it("renders split date and time labels", () => {
    mockUseCharacterSnapshots.mockReturnValue({
      isSuccess: true,
      data: {
        character_name: "Hero",
        snapshots: [
          {
            id: 1,
            fetched_at: "2026-06-01T12:00:00Z",
            is_current: false,
            changes: [],
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

    const timeEl = screen.getByText("Jun 1").closest("time");
    expect(timeEl).toBeInTheDocument();
    expect(timeEl).toHaveTextContent(/\d{1,2}:\d{2}/);
  });

  it("applies change-count color classes to unselected dots", () => {
    mockUseCharacterSnapshots.mockReturnValue({
      isSuccess: true,
      data: {
        character_name: "Hero",
        snapshots: [
          {
            id: 1,
            fetched_at: "2026-06-01T12:00:00Z",
            is_current: false,
            changes: [{ kind: "changed", label: "A" }],
          },
          {
            id: 2,
            fetched_at: "2026-06-03T12:00:00Z",
            is_current: true,
            changes: [
              { kind: "new", label: "B" },
              { kind: "new", label: "C" },
              { kind: "new", label: "D" },
              { kind: "new", label: "E" },
            ],
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

    const dot1 = screen.getByTestId("snapshot-dot-1");
    expect(dot1).toHaveAttribute("data-change-tier", "minimal");
    expect(dot1.className).toContain(snapshotDotColorClass(1).split(" ")[0]);

    const dotCurrent = screen.getByTestId("snapshot-dot-current");
    expect(dotCurrent).toHaveAttribute("data-change-tier", "moderate");
  });

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
    expect(screen.getByTestId("snapshot-changes-toggle")).toHaveTextContent("1 change");
    expect(screen.queryByTestId("snapshot-change-list")).not.toBeInTheDocument();

    await user.click(screen.getByTestId("snapshot-changes-toggle"));
    expect(screen.getByTestId("snapshot-change-list")).toHaveTextContent("+ Gold Ring");

    await user.click(screen.getByTestId("snapshot-dot-1"));
    expect(onSelect).toHaveBeenCalledWith(1);
  });

  it("hides change list by default when changes exist", () => {
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

    expect(screen.getByTestId("snapshot-changes-toggle")).toBeInTheDocument();
    expect(screen.queryByTestId("snapshot-change-list")).not.toBeInTheDocument();
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
