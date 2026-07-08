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
  implicit_mod_details: [],
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

function requestUrl(input: RequestInfo | URL): string {
  if (typeof input === "string") return input;
  if (input instanceof URL) return input.href;
  return (input as Request).url;
}

const failedPriceJob = {
  status: "failed" as const,
  step: "",
  message: "test",
  result: null,
  error: "test",
  user_id: "u1",
  item_id: "i1",
  league: "Dawn of the Hunt",
};

/** Default API behaviour: pricing lookup, async estimate POST/GET, trade + item-text. */
function installFetchMock(itemText: string) {
  return vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
    const u = requestUrl(input);
    if (u.includes("/api/pricing/lookup")) {
      return Promise.resolve(
        new Response(
          JSON.stringify({ league: "Dawn of the Hunt", prices: { i1: null } }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      );
    }
    if (u.includes("/api/pricing/currency-rates")) {
      return Promise.resolve(
        new Response(
          JSON.stringify({
            league: "Dawn of the Hunt",
            chaos_per_divine: 200,
            chaos_per_exalted: 8,
            exalted_per_divine: 25,
            source: "test",
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      );
    }
    if (u.includes("/api/pricing/estimate/item")) {
      return Promise.resolve(new Response(null, { status: 204 }));
    }
    if (u.includes("/api/pricing/estimate/")) {
      return Promise.resolve(
        new Response(JSON.stringify(failedPriceJob), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );
    }
    if (u.includes("/api/pricing/estimate") && init?.method === "POST") {
      return Promise.resolve(
        new Response(
          JSON.stringify({ job_id: "00000000-0000-0000-0000-000000000099", deduped: false }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      );
    }
    if (u.includes("/api/trade/search")) {
      return Promise.resolve(
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
    }
    if (u.includes("item-text")) {
      return Promise.resolve(
        new Response(JSON.stringify({ text: itemText }), {
          status: 200,
          headers: { "Content-Type": "application/json" } },
        ),
      );
    }
    return Promise.resolve(new Response("unmocked: " + u, { status: 500 }));
  });
}

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
    installFetchMock("");
    renderPane(testItem);
    expect(screen.getAllByText(/doom horn/i).length).toBeGreaterThan(0);
    // PNG snapshot markup duplicates key stats in an off-screen capture tree; allow multiples.
    expect(screen.getAllByText(/physical damage/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/120-280/).length).toBeGreaterThan(0);
    expect(screen.getByLabelText(/item details/i)).toHaveTextContent(/\+100\s+to maximum life/i);
    expect(screen.getAllByText(/requires/i).length).toBeGreaterThan(0);
  });

  it("renders granted skills with level", () => {
    installFetchMock("");
    renderPane({
      ...testItem,
      name: "Guiding Palm of the Eye",
      type_line: "Chiming Spirit Shield",
      base_type: "Chiming Spirit Shield",
      rarity: "Unique",
      granted_skills: ["Purity of Ice (lvl 18)"],
    });
    expect(screen.getAllByText(/Purity of Ice \(lvl 18\)/).length).toBeGreaterThan(0);
  });

  it("starts with tolerance pulled from prefs", () => {
    installFetchMock("");
    renderPane(testItem);
    const input = screen.getByLabelText(/exact tolerance/i) as HTMLInputElement;
    expect(input.value).toBe("15");
  });

  it("calls fetch when the exact trade button is clicked", async () => {
    const fetchMock = installFetchMock("");
    const openSpy = vi.spyOn(window, "open").mockReturnValue(null);

    const user = userEvent.setup();
    renderPane(testItem);
    await user.click(screen.getByRole("button", { name: /trade search/i }));

    await waitFor(() => {
      const hasTrade = fetchMock.mock.calls.some((c) => String(requestUrl(c[0]!)).includes("/api/trade"));
      expect(hasTrade).toBe(true);
    });
    const tradeCall = fetchMock.mock.calls.find((c) => String(requestUrl(c[0]!)).includes("/api/trade"))!;
    const body = JSON.parse((tradeCall[1] as RequestInit)?.body as string);
    expect(body.mode).toBe("exact");
    expect(body.league).toBe("Dawn of the Hunt");
    expect(openSpy).toHaveBeenCalled();
  });

  it("requests PoE2 item text from the API and shows a success message", async () => {
    const itemText = "Rarity: Rare\nDoom Horn\n";
    const fetchMock = installFetchMock(itemText);

    const user = userEvent.setup();
    renderPane(testItem);
    await user.click(screen.getByRole("button", { name: /copy poe2 item text/i }));

    await waitFor(() => {
      const textCall = fetchMock.mock.calls.find((c) => String(requestUrl(c[0]!)).includes("item-text"));
      expect(textCall).toBeDefined();
    });
    const textCall = fetchMock.mock.calls.find((c) => String(requestUrl(c[0]!)).includes("item-text"))!;
    const posted = JSON.parse((textCall[1] as RequestInit & { body?: string })?.body ?? "{}");
    expect(posted.item?.id).toBe("i1");
    await waitFor(() =>
      expect(screen.getByText(/PoE2 item text copied to clipboard/)).toBeInTheDocument(),
    );
  });
});
