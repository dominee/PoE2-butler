import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import type { CharacterDetail } from "@/api/types";
import { CharacterExportSnapshot, CharacterImageExportActions } from "./CharacterImageExport";

vi.mock("html-to-image", () => ({
  toPng: vi.fn().mockResolvedValue("data:image/png;base64,xx"),
}));

const detail: CharacterDetail = {
  summary: {
    id: "1",
    name: "Hero",
    realm: "poe2",
    class: "Ranger",
    level: 90,
    league: "Standard",
    experience: 1000,
  },
  equipped: [],
  gems: [],
  jewels: [],
  inventory: [],
};

describe("CharacterImageExportActions", () => {
  it("renders layout and theme selectors with export buttons", () => {
    render(<CharacterImageExportActions detail={detail} league="Standard" />);
    expect(screen.getByLabelText("Export layout")).toBeInTheDocument();
    expect(screen.getByLabelText("Export theme")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Copy PNG" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Download PNG" })).toBeInTheDocument();
  });

  it("renders export snapshot with theme test id", () => {
    render(
      <CharacterExportSnapshot
        detail={detail}
        league="Standard"
        layout="simple"
        theme="branded"
      />,
    );
    expect(screen.getByTestId("character-export-simple-branded")).toBeInTheDocument();
  });

  it("download uses file save, not clipboard", async () => {
    const user = userEvent.setup();
    const write = vi.spyOn(navigator.clipboard, "write").mockResolvedValue(undefined);
    const click = vi.fn();
    const origCreate = document.createElement.bind(document);
    vi.spyOn(document, "createElement").mockImplementation((tag, ...args) => {
      const el = origCreate(tag, ...args);
      if (tag === "a") {
        el.click = click;
      }
      return el;
    });

    render(<CharacterImageExportActions detail={detail} league="Standard" />);
    await user.click(screen.getByRole("button", { name: "Download PNG" }));

    expect(click).toHaveBeenCalled();
    expect(write).not.toHaveBeenCalled();
    expect(await screen.findByText("PNG downloaded")).toBeInTheDocument();

    write.mockRestore();
    vi.restoreAllMocks();
  });
});
