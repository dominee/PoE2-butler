import type { CurrencyRatesResponse, PriceEstimate } from "@/api/types";

export function formatChaos(value: number): string {
  if (value >= 1000) return `${(value / 1000).toFixed(1)}k`;
  if (value >= 100) return value.toFixed(0);
  if (value >= 10) return value.toFixed(1);
  return value.toFixed(2);
}

export function formatPriceEstimateLine(p: PriceEstimate): string {
  if (p.unit === "divine") return `${p.value.toFixed(2)} div`;
  if (p.unit === "exalted") return `${p.value.toFixed(2)} ex`;
  return `${formatChaos(p.chaos_equiv)}c`;
}

/** Chaos per divine/exalted for converting item value to div + ex display lines. */
export type CurrencyChaosPair = { chaosPerDivine: number; chaosPerExalted: number };

export function currencyRatesToChaosPair(
  r: CurrencyRatesResponse | null | undefined,
): CurrencyChaosPair | null {
  if (!r || r.chaos_per_divine <= 0 || r.chaos_per_exalted <= 0) return null;
  return { chaosPerDivine: r.chaos_per_divine, chaosPerExalted: r.chaos_per_exalted };
}

/** Primary display: div with ex in brackets; falls back to chaos when rates are missing. */
export function formatChaosAsDivExLine(
  chaosEquiv: number,
  rates: CurrencyChaosPair | null | undefined,
): string {
  if (!rates || chaosEquiv <= 0) return `${formatChaos(chaosEquiv)}c`;
  const div = chaosEquiv / rates.chaosPerDivine;
  const ex = chaosEquiv / rates.chaosPerExalted;
  return `${div.toFixed(2)} div (${ex.toFixed(1)} ex)`;
}

/** Mean of mod lines that have a roll percentage (implicit + explicit). */
export function computeItemScore(pcts: (number | null)[]): number | null {
  const valid = pcts.filter((p): p is number => p != null);
  if (valid.length === 0) {
    return null;
  }
  return Math.round(valid.reduce((a, b) => a + b, 0) / valid.length);
}
