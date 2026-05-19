import type { CurrencyRatesResponse, PriceEstimate } from "@/api/types";

export function formatChaos(value: number): string {
  if (value >= 1000) return `${Math.ceil(value / 1000)}k`;
  return `${Math.ceil(value)}`;
}

export function formatPriceEstimateLine(p: PriceEstimate): string {
  if (p.unit === "divine") return `${Math.ceil(p.value)} div`;
  if (p.unit === "exalted") return `${Math.ceil(p.value)} ex`;
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
  const parts = getChaosEquivDisplayParts(chaosEquiv, rates);
  if (parts.kind === "chaos") return parts.text;
  return `${parts.divAmount} div (${parts.exAmount} ex)`;
}

export type ChaosEquivDisplayParts =
  | { kind: "divEx"; divAmount: string; exAmount: string }
  | { kind: "chaos"; text: string };

/** Structured chaos→div+ex for styled UI (numbers + unit words). */
export function getChaosEquivDisplayParts(
  chaosEquiv: number,
  rates: CurrencyChaosPair | null | undefined,
): ChaosEquivDisplayParts {
  if (!rates || chaosEquiv <= 0) {
    return { kind: "chaos", text: `${formatChaos(chaosEquiv)}c` };
  }
  const div = chaosEquiv / rates.chaosPerDivine;
  const ex = chaosEquiv / rates.chaosPerExalted;
  return { kind: "divEx", divAmount: String(Math.ceil(div)), exAmount: String(Math.ceil(ex)) };
}

/** Mean of mod lines that have a roll percentage (implicit + explicit). */
export function computeItemScore(pcts: (number | null)[]): number | null {
  const valid = pcts.filter((p): p is number => p != null);
  if (valid.length === 0) {
    return null;
  }
  return Math.round(valid.reduce((a, b) => a + b, 0) / valid.length);
}
