import { describe, expect, it, vi } from "vitest";

import { closeExternalTab, navigateExternalTab, showExternalTabLoading } from "./openExternalTab";

function makeTab(overrides: Partial<Window> = {}): Window {
  const doc = { open: vi.fn(), write: vi.fn(), close: vi.fn() };
  return {
    closed: false,
    opener: null,
    location: { href: "" },
    close: vi.fn(),
    document: doc,
    ...overrides,
  } as unknown as Window;
}

describe("showExternalTabLoading", () => {
  it("writes loading HTML with the given message into the tab", () => {
    const tab = makeTab();
    showExternalTabLoading(tab, "Creating trade search…");
    const doc = tab.document as unknown as ReturnType<typeof vi.fn> & {
      open: ReturnType<typeof vi.fn>;
      write: ReturnType<typeof vi.fn>;
      close: ReturnType<typeof vi.fn>;
    };
    expect((doc as unknown as { write: ReturnType<typeof vi.fn> }).write).toHaveBeenCalledOnce();
    const html = ((doc as unknown as { write: ReturnType<typeof vi.fn> }).write.mock.calls[0][0] as string);
    expect(html).toContain("Creating trade search");
    expect(html).toContain("spinner");
  });

  it("does nothing when tab is null", () => {
    expect(() => showExternalTabLoading(null, "msg")).not.toThrow();
  });

  it("does nothing when tab is already closed", () => {
    const tab = makeTab({ closed: true });
    showExternalTabLoading(tab, "msg");
    const doc = tab.document as unknown as { write: ReturnType<typeof vi.fn> };
    expect(doc.write).not.toHaveBeenCalled();
  });

  it("escapes HTML in the message", () => {
    const tab = makeTab();
    showExternalTabLoading(tab, "<script>alert(1)</script>");
    const doc = tab.document as unknown as { write: ReturnType<typeof vi.fn> };
    const html = doc.write.mock.calls[0][0] as string;
    expect(html).not.toContain("<script>");
    expect(html).toContain("&lt;script&gt;");
  });
});

describe("navigateExternalTab", () => {
  it("sets location.href when tab is open", () => {
    const tab = makeTab();
    const opened = navigateExternalTab(tab, "https://example.com");
    expect(opened).toBe(true);
    expect((tab.location as { href: string }).href).toBe("https://example.com");
  });

  it("falls back to window.open when tab is null", () => {
    const openSpy = vi.spyOn(window, "open").mockReturnValue(makeTab());
    const opened = navigateExternalTab(null, "https://example.com");
    expect(opened).toBe(true);
    expect(openSpy).toHaveBeenCalled();
    openSpy.mockRestore();
  });
});

describe("closeExternalTab", () => {
  it("closes an open tab", () => {
    const tab = makeTab();
    closeExternalTab(tab);
    expect((tab.close as ReturnType<typeof vi.fn>)).toHaveBeenCalled();
  });

  it("does nothing for null tab", () => {
    expect(() => closeExternalTab(null)).not.toThrow();
  });
});
