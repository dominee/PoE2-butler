import { describe, expect, it } from "vitest";

import type { ModDetail } from "@/api/types";

import { computeModRollMetrics, modQuality, primaryStatValueFromMod } from "./modRollMetrics";

describe("primaryStatValueFromMod", () => {
  it("parses a single value and range average", () => {
    expect(primaryStatValueFromMod("+100 to maximum Life")).toBe(100);
    expect(primaryStatValueFromMod("Adds 5 to 12 Physical Damage")).toBeCloseTo(8.5);
  });
});

describe("computeModRollMetrics", () => {
  it("computes within-tier and vs T1 when both exist", () => {
    const detail: ModDetail = {
      name: "life",
      tier: 3,
      level: null,
      magnitudes: [{ hash: "x", min: 80, max: 99, t1_max: 120 }],
    };
    expect(computeModRollMetrics("+90 to maximum Life", detail).withinTierPct).toBe(
      Math.round(((90 - 80) / (99 - 80)) * 100),
    );
    const at100 = computeModRollMetrics("+100 to maximum Life", detail);
    expect(at100.vsT1Pct).toBe(83);
    expect(at100.hasTierRange).toBe(true);
    expect(at100.hasT1).toBe(true);
  });

  it("falls back to within-tier when no t1_max", () => {
    const detail: ModDetail = {
      name: "x",
      tier: 1,
      level: null,
      magnitudes: [{ hash: "x", min: 10, max: 20, t1_max: null }],
    };
    const m = computeModRollMetrics("+15% increased", detail);
    expect(m.vsT1Pct).toBeNull();
    expect(m.withinTierPct).toBe(50);
    expect(modQuality("+15% increased", detail)).toBe(50);
  });
});
