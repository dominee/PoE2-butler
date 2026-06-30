import { describe, expect, it } from "vitest";

import { formatExChaosRate } from "./currencyRateDisplay";

describe("formatExChaosRate", () => {
  it("shows chaos per ex when 1 ex is worth at least 1 chaos", () => {
    expect(formatExChaosRate(8)).toEqual({
      leftAmount: "1",
      leftUnit: "ex",
      rightAmount: "8",
      rightUnit: "chaos",
    });
  });

  it("shows ex per chaos when 1 ex is worth less than 1 chaos", () => {
    const rate = 1 / 36;
    expect(formatExChaosRate(rate)).toEqual({
      leftAmount: "36",
      leftUnit: "ex",
      rightAmount: "1",
      rightUnit: "chaos",
    });
  });
});
