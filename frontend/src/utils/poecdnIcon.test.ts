import { describe, expect, it } from "vitest";

import { itemIconForCanvasProxy } from "./poecdnIcon";

describe("itemIconForCanvasProxy", () => {
  it("rewrites web.poecdn.com https URLs to the API proxy", () => {
    const u = "https://web.poecdn.com/gen/image/abc/1/Foo.png";
    expect(itemIconForCanvasProxy(u)).toBe(`/api/cdn/poecdn?u=${encodeURIComponent(u)}`);
  });

  it("passes through other URLs unchanged", () => {
    expect(itemIconForCanvasProxy("https://other.example.com/x.png")).toBe(
      "https://other.example.com/x.png",
    );
  });

  it("returns null for null or empty", () => {
    expect(itemIconForCanvasProxy(null)).toBeNull();
    expect(itemIconForCanvasProxy("")).toBeNull();
  });
});
