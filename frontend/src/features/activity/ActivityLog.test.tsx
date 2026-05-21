import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { ActivityResponse, Item } from "@/api/types";

// Mock the hooks module so we control what useActivity returns without a network.
vi.mock("@/api/hooks", () => ({
  useActivity: vi.fn(),
}));

import { useActivity } from "@/api/hooks";
import { ActivityLog } from "./ActivityLog";

const mockUseActivity = useActivity as ReturnType<typeof vi.fn>;

// ── minimal item factory ───────────────────────────────────────────────────────
function makeItem(id: string, name: string): Item {
  return {
    id,
    inventory_id: null,
    w: 1,
    h: 1,
    x: null,
    y: null,
    item_class: null,
    name,
    type_line: "Stellar Amulet",
    base_type: "Stellar Amulet",
    rarity: "Rare",
    ilvl: 80,
    identified: true,
    corrupted: false,
    flavour_text: null,
    implicit_mod_range_hints: [],
    explicit_mod_range_hints: [],
    trailer_note: null,
    properties: [],
    requirements: [],
    implicit_mods: [],
    implicit_mod_details: [],
    explicit_mods: [],
    explicit_mod_details: [],
    rune_mods: [],
    enchant_mods: [],
    crafted_mods: [],
    sockets: [],
    socketed_items: [],
    stack_size: null,
    max_stack_size: null,
    icon: null,
  };
}

function makeActivityResponse(overrides: Partial<ActivityResponse> = {}): ActivityResponse {
  return {
    league: "Fate of the Vaal",
    has_prev: true,
    total_new: 0,
    total_changed: 0,
    entries: [],
    gear_entries: [],
    ...overrides,
  };
}

function setupMock(response: ActivityResponse | null, isLoading = false) {
  mockUseActivity.mockReturnValue({
    data: response ?? undefined,
    isLoading,
    error: null,
  });
}

describe("ActivityLog — collapsed state (default)", () => {
  it("renders an expand toggle button", () => {
    setupMock(null);
    render(<ActivityLog league="Fate of the Vaal" onSelectItem={vi.fn()} />);
    expect(screen.getByTitle("Expand activity log")).toBeInTheDocument();
  });

  it("shows an event count badge when there are events", () => {
    setupMock(
      makeActivityResponse({
        total_new: 3,
        total_changed: 2,
        entries: [
          {
            tab_id: "t1",
            tab_name: "Dump Tab",
            new_items: [makeItem("a", "Amulet A"), makeItem("b", "Ring B"), makeItem("c", "Helm C")],
            changed_items: [
              { old: makeItem("d", "Old"), new: makeItem("d", "New") },
              { old: makeItem("e", "Old2"), new: makeItem("e", "New2") },
            ],
            removed_items: [],
          },
        ],
      }),
    );
    render(<ActivityLog league="Fate of the Vaal" onSelectItem={vi.fn()} />);
    // Badge should show total = 5
    expect(screen.getByText("5")).toBeInTheDocument();
  });

  it("caps the badge at 99+ for large event counts", () => {
    const manyItems = Array.from({ length: 100 }, (_, i) => makeItem(`i${i}`, `Item ${i}`));
    setupMock(
      makeActivityResponse({
        total_new: 100,
        entries: [
          {
            tab_id: "t1",
            tab_name: "Dump",
            new_items: manyItems,
            changed_items: [],
            removed_items: [],
          },
        ],
      }),
    );
    render(<ActivityLog league="Fate of the Vaal" onSelectItem={vi.fn()} />);
    expect(screen.getByText("99+")).toBeInTheDocument();
  });
});

describe("ActivityLog — expanded state", () => {
  it("expands when the toggle is clicked", async () => {
    const user = userEvent.setup();
    setupMock(makeActivityResponse({ has_prev: false }));
    render(<ActivityLog league="Fate of the Vaal" onSelectItem={vi.fn()} />);
    await user.click(screen.getByTitle("Expand activity log"));
    // After expand, toggle title changes
    expect(screen.getByTitle("Collapse activity log")).toBeInTheDocument();
  });

  it("shows no-previous-snapshot message when has_prev=false", async () => {
    const user = userEvent.setup();
    setupMock(makeActivityResponse({ has_prev: false }));
    render(<ActivityLog league="Fate of the Vaal" onSelectItem={vi.fn()} />);
    await user.click(screen.getByTitle("Expand activity log"));
    expect(screen.getByText(/no previous snapshot/i)).toBeInTheDocument();
  });

  it("shows 'no changes' message when has_prev=true but no events", async () => {
    const user = userEvent.setup();
    setupMock(makeActivityResponse({ has_prev: true, total_new: 0, total_changed: 0 }));
    render(<ActivityLog league="Fate of the Vaal" onSelectItem={vi.fn()} />);
    await user.click(screen.getByTitle("Expand activity log"));
    expect(screen.getByText(/no changes since last refresh/i)).toBeInTheDocument();
  });

  it("shows loading indicator while fetching", async () => {
    const user = userEvent.setup();
    setupMock(null, true);
    render(<ActivityLog league="Fate of the Vaal" onSelectItem={vi.fn()} />);
    await user.click(screen.getByTitle("Expand activity log"));
    expect(screen.getByText(/loading/i)).toBeInTheDocument();
  });
});

describe("ActivityLog — new / changed / removed items", () => {
  async function expandWithEntries(entries: ActivityResponse["entries"]) {
    const user = userEvent.setup();
    const totalNew = entries.reduce((n, e) => n + e.new_items.length, 0);
    const totalChanged = entries.reduce((n, e) => n + e.changed_items.length, 0);
    setupMock(
      makeActivityResponse({ has_prev: true, total_new: totalNew, total_changed: totalChanged, entries }),
    );
    const onSelect = vi.fn();
    render(<ActivityLog league="Fate of the Vaal" onSelectItem={onSelect} />);
    await user.click(screen.getByTitle("Expand activity log"));
    return { user, onSelect };
  }

  it("renders new items with their names", async () => {
    await expandWithEntries([
      {
        tab_id: "t1",
        tab_name: "Tab One",
        new_items: [makeItem("n1", "Crown of the Tyrant")],
        changed_items: [],
        removed_items: [],
      },
    ]);
    expect(screen.getByText(/crown of the tyrant/i)).toBeInTheDocument();
    expect(screen.getByText(/tab one/i)).toBeInTheDocument();
  });

  it("renders changed items", async () => {
    await expandWithEntries([
      {
        tab_id: "t2",
        tab_name: "Tab Two",
        new_items: [],
        changed_items: [{ old: makeItem("c1", "Old Ring"), new: makeItem("c1", "New Ring") }],
        removed_items: [],
      },
    ]);
    // Shows the new version's name
    expect(screen.getByText(/new ring/i)).toBeInTheDocument();
  });

  it("renders removed items with strikethrough hint", async () => {
    await expandWithEntries([
      {
        tab_id: "t3",
        tab_name: "Tab Three",
        new_items: [],
        changed_items: [],
        removed_items: [makeItem("r1", "Deleted Sword")],
      },
    ]);
    expect(screen.getByText(/deleted sword.*removed/i)).toBeInTheDocument();
  });

  it("calls onSelectItem when a new item row is clicked", async () => {
    const item = makeItem("click1", "Clickable Item");
    const { user, onSelect } = await expandWithEntries([
      {
        tab_id: "t4",
        tab_name: "Tab",
        new_items: [item],
        changed_items: [],
        removed_items: [],
      },
    ]);
    await user.click(screen.getByText(/clickable item/i));
    expect(onSelect).toHaveBeenCalledWith(item);
  });

  it("skips tabs with zero total events", async () => {
    await expandWithEntries([
      {
        tab_id: "empty",
        tab_name: "Empty Tab",
        new_items: [],
        changed_items: [],
        removed_items: [],
      },
      {
        tab_id: "active",
        tab_name: "Active Tab",
        new_items: [makeItem("x1", "Something")],
        changed_items: [],
        removed_items: [],
      },
    ]);
    expect(screen.queryByText(/empty tab/i)).not.toBeInTheDocument();
    expect(screen.getByText(/active tab/i)).toBeInTheDocument();
  });
});

describe("ActivityLog — gear section", () => {
  it("shows a Gear heading and character name when gear_entries are present", async () => {
    const user = userEvent.setup();
    setupMock(
      makeActivityResponse({
        has_prev: true,
        total_new: 1,
        gear_entries: [
          {
            tab_id: "Marauder",
            tab_name: "Marauder",
            new_items: [makeItem("g1", "Iron Gauntlets")],
            changed_items: [],
            removed_items: [],
          },
        ],
      }),
    );
    render(<ActivityLog league="Fate of the Vaal" onSelectItem={vi.fn()} />);
    await user.click(screen.getByTitle("Expand activity log"));
    expect(screen.getByText(/gear/i)).toBeInTheDocument();
    expect(screen.getByText(/marauder/i)).toBeInTheDocument();
    expect(screen.getByText(/iron gauntlets/i)).toBeInTheDocument();
  });

  it("hides the Gear heading when gear_entries is empty", async () => {
    const user = userEvent.setup();
    setupMock(makeActivityResponse({ has_prev: true, gear_entries: [] }));
    render(<ActivityLog league="Fate of the Vaal" onSelectItem={vi.fn()} />);
    await user.click(screen.getByTitle("Expand activity log"));
    // "Gear" heading only appears when there are entries
    expect(screen.queryByText(/^gear$/i)).not.toBeInTheDocument();
  });
});
