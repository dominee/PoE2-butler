import type { PriceEstimate } from "@/api/types";
import { type CurrencyChaosPair, formatChaos, formatChaosAsDivExLine } from "./itemMetrics";

export interface PriceBadgeProps {
  price: PriceEstimate | null | undefined;
  threshold?: number;
  compact?: boolean;
  /** When set (e.g. from poe.ninja), show `div (ex)` instead of chaos only. */
  currencyChaos?: CurrencyChaosPair | null;
}

export function PriceBadge({ price, threshold, compact, currencyChaos }: PriceBadgeProps) {
  if (!price) return null;
  const valuable = threshold != null && price.chaos_equiv >= threshold;
  const label = currencyChaos
    ? formatChaosAsDivExLine(price.chaos_equiv, currencyChaos)
    : `${formatChaos(price.chaos_equiv)}c`;
  return (
    <span
      className={[
        "inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 text-[10px] font-medium",
        valuable
          ? "border-emerald-400/70 bg-emerald-500/10 text-emerald-200"
          : "border-ink-700 bg-ink-800 text-parchment-100/90",
        compact ? "uppercase" : "",
      ].join(" ")}
      title={`${price.chaos_equiv.toFixed(2)} chaos equivalent · source: ${price.source}`}
      data-testid="price-badge"
    >
      <span aria-hidden="true">◈</span>
      <span className="font-mono tabular-nums">{label}</span>
    </span>
  );
}
