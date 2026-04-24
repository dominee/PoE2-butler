import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { Item, Prefs } from "@/api/types";
import { ItemDetailPane } from "./ItemDetailPane";

const testItem: Item = {
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
  properties: [{ name: "Physical Damage", value: "120-280" }],
  requirements: [{ name: "Level", value: "72" }],
  implicit_mods: [],
  explicit_mods: ["+100 to maximum Life"],
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

const prefs: Prefs = { trade_tolerance_pct: 15, preferred_league: null, valuable_threshold_chaos: 10 };

function renderPane(item: Item | null) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <ItemDetailPane item={item} league="Dawn of the Hunt" prefs={prefs} />
    </QueryClientProvider>,
  );
}

describe("ItemDetailPane", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("shows an empty state when no item is selected", () => {
    renderPane(null);
    expect(screen.getByText(/select an item/i)).toBeInTheDocument();
  });

  it("renders item properties, requirements and explicit mods", () => {
    renderPane(testItem);
    expect(screen.getAllByText(/doom horn/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/physical damage/i)).toBeInTheDocument();
    expect(screen.getByText(/120-280/)).toBeInTheDocument();
    expect(screen.getByLabelText(/item details/i)).toHaveTextContent(/\+100\s+to maximum life/i);
    expect(screen.getByText(/requires/i)).toBeInTheDocument();
  });

  it("starts with tolerance pulled from prefs", () => {
    renderPane(testItem);
    const input = screen.getByLabelText(/exact tolerance/i) as HTMLInputElement;
    expect(input.value).toBe("15");
  });

  it("calls fetch when the exact trade button is clicked", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            league: "Dawn of the Hunt",
            prices: { i1: null },
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            mode: "exact",
            league: "Dawn of the Hunt",
            url: "https://www.pathofexile.com/trade2/search/poe2/Dawn%20of%20the%20Hunt",
            payload: {},
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      );
    const openSpy = vi.spyOn(window, "open").mockReturnValue(null);

    const user = userEvent.setup();
    renderPane(testItem);
    await user.click(screen.getByRole("button", { name: /same item on trade/i }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    const [, init] = fetchMock.mock.calls.at(-1)!;
    const body = JSON.parse((init?.body as string) ?? "{}");
    expect(body.mode).toBe("exact");
    expect(body.league).toBe("Dawn of the Hunt");
    expect(openSpy).toHaveBeenCalled();
  });

  it("requests PoE2 item text from the API and shows a success message", async () => {
    const itemText = "Rarity: Rare\nDoom Horn\n";
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({ league: "Dawn of the Hunt", prices: { i1: null } }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ text: itemText }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );

    const user = userEvent.setup();
    renderPane(testItem);
    await user.click(screen.getByRole("button", { name: /copy poe2 item text/i }));

    const posted = JSON.parse(
      (fetchMock.mock.calls[1]![1] as RequestInit & { body?: string })?.body ?? "{}",
    );
    expect(posted.item?.id).toBe("i1");
    expect(String(fetchMock.mock.calls[1]![0])).toContain("item-text");
    await waitFor(() =>
      expect(screen.getByText(/PoE2 item text copied to clipboard/)).toBeInTheDocument(),
    );
  });
});
