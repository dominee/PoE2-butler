import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import type { CharacterDetail } from "@/api/types";
import { CharacterStatSummary } from "./CharacterStatSummary";

const base: CharacterDetail = {
  summary: {
    id: "1",
    name: "H",
    realm: "pc",
    class: "A",
    level: 1,
    league: null,
    experience: null,
  },
  equipped: [],
  inventory: [],
  stat_summary: { sections: [] },
};

describe("CharacterStatSummary", () => {
  it("shows a brief stat strip when collapsed and the full table when expanded", async () => {
    const user = userEvent.setup();
    const detail: CharacterDetail = {
      ...base,
      stat_summary: {
        sections: [
          {
            id: "resistances",
            label: "Resistances",
            sort_index: 1,
            rows: [
              {
                key: "+#% to all ...",
                label: "+20% to all Elemental Resistances",
                values: [20],
              },
            ],
          },
        ],
      },
    };
    render(<CharacterStatSummary detail={detail} />);

    const brief = screen.getByTestId("stat-summary-brief");
    expect(brief).toBeInTheDocument();
    const resHeading = within(brief).getByText("Resistances");
    expect(resHeading).toBeInTheDocument();
    expect(within(brief).getByText("All res")).toBeInTheDocument();
    expect(within(brief).getByText("20%")).toBeInTheDocument();
    expect(
      within(brief).queryByText("+20% to all Elemental Resistances")
    ).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "All stats" }));
    expect(screen.getByText("Resistances")).toBeInTheDocument();
    expect(screen.getByText("+20% to all Elemental Resistances")).toBeInTheDocument();
    expect(screen.getByText("20%")).toBeInTheDocument();
    expect(screen.queryByTestId("stat-summary-brief")).not.toBeInTheDocument();
  });

  it("shows an empty state when there are no sections", () => {
    render(<CharacterStatSummary detail={base} />);
    expect(screen.getByText(/no cumulative stats from equipment yet/i)).toBeInTheDocument();
  });
});
