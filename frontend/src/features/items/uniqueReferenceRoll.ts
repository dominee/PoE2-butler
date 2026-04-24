/**
 * Type-range roll % from bundled ``referenceRangeText`` (poe2db / wiki) vs the mod line.
 * Global “item quality” = mean of per-line scores when references exist.
 */

import type { Item } from "@/api/types";
import { stripTags } from "@/utils/modText";

import { primaryStatValueFromMod } from "./modRollMetrics";

const EM = "\u2014";

function normalizeRefDashes(s: string): string {
  return s.replace(/[\u2013\u2014–—-]/g, EM);
}

export interface ParsedTypeRange {
  min: number;
  max: number;
}

/**
 * Parse the right-column reference string, e.g. ``+(40—60)``, ``(20—30)%``, ``(1—3) Slots``.
 */
export function parseTypeRangeFromHint(ref: string): ParsedTypeRange | null {
  const t = normalizeRefDashes(ref.trim());
  if (!t.includes(EM)) {
    return null;
  }
  if (/\s*slots?$/i.test(t)) {
    const m1 = t.match(
      new RegExp(`^\\+?\\(([0-9.]+)${EM}([0-9.]+)\\)(?:\\s*Slots?)?$`, "i"),
    );
    if (m1) {
      const a = Number.parseFloat(m1[1]!);
      const b = Number.parseFloat(m1[2]!);
      if (Number.isFinite(a) && Number.isFinite(b)) {
        return { min: Math.min(a, b), max: Math.max(a, b) };
      }
    }
  }
  const m1 = t.match(
    new RegExp(`^\\+\\(([0-9.]+)${EM}([0-9.]+)\\)(%?)$`, "i"),
  );
  if (m1) {
    const a = Number.parseFloat(m1[1]!);
    const b = Number.parseFloat(m1[2]!);
    if (Number.isFinite(a) && Number.isFinite(b)) {
      return { min: Math.min(a, b), max: Math.max(a, b) };
    }
  }
  const m2 = t.match(
    new RegExp(`^\\(([0-9.]+)${EM}([0-9.]+)\\)(%?)$`, "i"),
  );
  if (m2) {
    const a = Number.parseFloat(m2[1]!);
    const b = Number.parseFloat(m2[2]!);
    if (Number.isFinite(a) && Number.isFinite(b)) {
      return { min: Math.min(a, b), max: Math.max(a, b) };
    }
  }
  return null;
}

function charmCountFromMod(mod: string): number | null {
  const plain = stripTags(mod);
  const m1 = plain.match(/Has\s+(\d+(?:\.\d+)?)\s*Charm/i) ?? plain.match(/(\d+)\s*Charm\s*Slot/i);
  if (m1) {
    const n = Number.parseFloat(m1[1]!);
    return Number.isFinite(n) ? n : null;
  }
  return null;
}

function lineImpliesLowerIsBetter(mod: string): boolean {
  const l = stripTags(mod).toLowerCase();
  if (l.includes("reduced")) {
    return true;
  }
  return false;
}

function clamp0to100(t: number): number {
  if (Number.isNaN(t)) {
    return 0;
  }
  return Math.max(0, Math.min(100, Math.round(t)));
}

/**
 * 0–100: how close the rolled value is to the **best** end of the type range.
 * Null if the reference cannot be parsed or the instance value is unknown.
 */
export function uniqueTypeRollPercent(
  mod: string,
  referenceRangeText: string | null | undefined,
): number | null {
  if (!referenceRangeText?.trim()) {
    return null;
  }
  const range = parseTypeRangeFromHint(referenceRangeText);
  if (!range) {
    return null;
  }
  const { min, max } = range;
  if (max < min) {
    return null;
  }
  if (max === min) {
    return 100;
  }
  const lowerIsBetter = lineImpliesLowerIsBetter(mod);
  const useCharm =
    /\bSlots?\b/i.test(referenceRangeText) &&
    charmCountFromMod(mod) != null;
  const value: number | null = useCharm ? charmCountFromMod(mod) : primaryStatValueFromMod(mod);
  if (value == null || !Number.isFinite(value)) {
    return null;
  }
  if (lowerIsBetter) {
    return clamp0to100(((max - value) / (max - min)) * 100);
  }
  return clamp0to100(((value - min) / (max - min)) * 100);
}

/** Implicits, then explicits — same order as the detail pane. */
export function itemReferenceRollPcts(item: Item): (number | null)[] {
  if (item.rarity !== "Unique") {
    return [];
  }
  const ih = item.implicit_mod_range_hints ?? [];
  const eh = item.explicit_mod_range_hints ?? [];
  const im = item.implicit_mods.map((m, i) => uniqueTypeRollPercent(m, ih[i] ?? null));
  const ex = item.explicit_mods.map((m, i) => uniqueTypeRollPercent(m, eh[i] ?? null));
  return [...im, ...ex];
}

export function itemReferenceHasAggregate(pcts: (number | null)[]): boolean {
  return pcts.some((p) => p != null);
}
