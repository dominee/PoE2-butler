import { afterEach, describe, expect, it, vi } from "vitest";

import { copyTextToClipboard } from "./clipboard";

describe("copyTextToClipboard", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("uses navigator.clipboard.writeText when it succeeds", async () => {
    const w = vi.fn().mockResolvedValue(undefined);
    vi.stubGlobal("navigator", { clipboard: { writeText: w } });
    await copyTextToClipboard("hello");
    expect(w).toHaveBeenCalledWith("hello");
  });

  it("falls back to execCommand when clipboard is missing (non-secure origin)", async () => {
    vi.stubGlobal("navigator", { clipboard: undefined });
    const exec = vi.fn().mockReturnValue(true);
    // happy-dom / jsdom may not implement execCommand; assign for this test
    (document as unknown as { execCommand: (cmd: string) => boolean }).execCommand = exec;
    await copyTextToClipboard("fallback");
    expect(exec).toHaveBeenCalledWith("copy");
  });
});
