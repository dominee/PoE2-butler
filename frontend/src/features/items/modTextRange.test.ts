import { describe, expect, it } from "vitest";

import { modTextRangeHint } from "./modTextRange";

describe("modTextRangeHint", () => {
  it("finds 'X to Y' and dash ranges", () => {
    expect(modTextRangeHint("Adds 5 to 12 Physical Damage")).toBe("5 – 12");
    expect(modTextRangeHint("120-280 Physical")).toBe("120 – 280");
  });
});
