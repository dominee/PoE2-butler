/**
 * Roll % within the mod’s tier range vs % of global T1 max — used for stat bars and item score.
 */

import type { Item, ModDetail, ModMagnitude } from "@/api/types";
import { parseModParts } from "@/utils/modText";

export interface ModRollMetrics {
  /** Position within [min,max] for this affix tier (0–100). */
  withinTierPct: number | null;
  /** Rolled value as % of the best possible (T1) value for this stat hash. */
  vsT1Pct: number | null;
  hasTierRange: boolean;
  hasT1: boolean;
}

/** Single primary value from mod text (avg for “5 to 12” or “120-280”). */
export function primaryStatValueFromMod(modText: string): number | null {
  const parts = parseModParts(modText);
  const singles: number[] = [];
  for (const p of parts) {
    if (!p.isNum) {
      continue;
    }
    const raw = p.text.replace("%", "");
    if (raw.includes("-") && /^\d/.test(raw) && !raw.includes(" to ")) {
      const bits = raw.split("-");
      if (bits.length === 2) {
        const a = Number.parseFloat(bits[0]!);
        const b = Number.parseFloat(bits[1]!);
        if (Number.isFinite(a) && Number.isFinite(b)) {
          return (a + b) / 2;
        }
      }
    }
    const n = Number.parseFloat(raw);
    if (Number.isFinite(n)) {
      singles.push(Math.abs(n));
    }
  }
  if (singles.length >= 2) {
    return (singles[0]! + singles[1]!) / 2;
  }
  if (singles.length === 1) {
    return singles[0]!;
  }
  return null;
}

function rollWithinTier(value: number, min: number, max: number): number {
  if (max <= min) {
    return 100;
  }
  return Math.round(((value - min) / (max - min)) * 100);
}

function pickMagnitude(detail: ModDetail | undefined): ModMagnitude | undefined {
  return detail?.magnitudes?.[0];
}

export function computeModRollMetrics(mod: string, detail: ModDetail | undefined): ModRollMetrics {
  const mag = pickMagnitude(detail);
  const value = primaryStatValueFromMod(mod);
  if (value == null || !mag) {
    return {
      withinTierPct: null,
      vsT1Pct: null,
      hasTierRange: false,
      hasT1: false,
    };
  }

  const hasRange = mag.min != null && mag.max != null && mag.min !== mag.max;
  const withinTierPct =
    hasRange && mag.min != null && mag.max != null
      ? rollWithinTier(value, mag.min, mag.max)
      : null;

  const t1 = mag.t1_max;
  const vsT1Pct =
    t1 != null && t1 > 0 ? Math.round((value / t1) * 100) : null;

  return {
    withinTierPct,
    vsT1Pct,
    hasTierRange: Boolean(hasRange),
    hasT1: t1 != null && t1 > 0,
  };
}

/** One number for aggregate item score: prefer T1 comparison, else within-tier. */
export function modQuality(mod: string, detail: ModDetail | undefined): number | null {
  const m = computeModRollMetrics(mod, detail);
  if (m.vsT1Pct != null) {
    return m.vsT1Pct;
  }
  if (m.withinTierPct != null) {
    return m.withinTierPct;
  }
  return null;
}

export function itemRollScoreState(item: Item): {
  modPcts: (number | null)[];
  showAggregate: boolean;
} {
  const imDetails = item.implicit_mod_details ?? [];
  const exDetails = item.explicit_mod_details ?? [];
  const im = item.implicit_mods.map((m, i) => modQuality(m, imDetails[i]));
  const ex = item.explicit_mods.map((m, i) => modQuality(m, exDetails[i]));
  const modPcts = [...im, ...ex];
  const showAggregate = modPcts.some((p) => p != null);
  return { modPcts, showAggregate };
}
