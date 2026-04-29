import type { PriceEstimate } from "@/api/types";
import type { CurrencyChaosPair } from "@/features/items/itemMetrics";
import { formatChaos, getChaosEquivDisplayParts } from "@/features/items/itemMetrics";

/** Chaos→div (+ex in parens) with bright numbers and unit labels (matches stat value contrast). */
export function DivExPriceText({
  chaosEquiv,
  rates,
  valuable = false,
  className = "",
}: {
  chaosEquiv: number;
  rates: CurrencyChaosPair | null | undefined;
  /** When true, use emerald tint (valuable ``PriceBadge``). */
  valuable?: boolean;
  className?: string;
}) {
  const p = getChaosEquivDisplayParts(chaosEquiv, rates);
  const n = valuable ? "font-mono tabular-nums text-emerald-100" : "font-mono tabular-nums text-white/92";
  const u = valuable ? "text-emerald-200/95" : "text-white/88";
  const paren = valuable ? "text-emerald-200/75" : "text-white/72";
  if (p.kind === "chaos") {
    return (
      <span className={`${n} ${className}`.trim()}>{p.text}</span>
    );
  }
  return (
    <span className={className}>
      <span className={n}>{p.divAmount}</span>
      <span className={u}> div </span>
      <span className={paren}>(</span>
      <span className={n}>{p.exAmount}</span>
      <span className={u}> ex)</span>
    </span>
  );
}

/** Refined / snapshot line when only a ``PriceEstimate`` is available (no div+ex pair). */
export function PriceEstimateBrightText({
  estimate,
  valuable = false,
}: {
  estimate: PriceEstimate;
  valuable?: boolean;
}) {
  const n = valuable ? "font-mono tabular-nums text-emerald-100" : "font-mono tabular-nums text-white/92";
  const u = valuable ? "text-emerald-200/95" : "text-white/88";
  if (estimate.unit === "chaos") {
    return <span className={n}>{formatChaos(estimate.chaos_equiv)}c</span>;
  }
  const v = estimate.value.toFixed(2);
  const word = estimate.unit === "divine" ? "div" : "ex";
  return (
    <span>
      <span className={n}>{v}</span>
      <span className={u}> {word}</span>
    </span>
  );
}
