import type { PriceEstimate } from "@/api/types";
import { type CurrencyChaosPair, formatChaos } from "./itemMetrics";
import { DivExPriceText } from "./DivExPriceText";

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
  const methodLabel =
    price.estimate_method === "trade_median"
      ? `trade median${price.sample_size != null ? ` · ${price.sample_size} listings` : ""}`
      : price.estimate_method === "poe2scout"
        ? "poe2scout"
        : price.estimate_method === "aggregator"
          ? "aggregator"
          : null;
  const label = currencyChaos ? (
    <DivExPriceText chaosEquiv={price.chaos_equiv} rates={currencyChaos} valuable={valuable} />
  ) : (
    `${formatChaos(price.chaos_equiv)}c`
  );
  const titleParts = [`${Math.ceil(price.chaos_equiv)} chaos equivalent`, `source: ${price.source}`];
  if (methodLabel) {
    titleParts.push(`method: ${methodLabel}`);
  }
  return (
    <span
      className={[
        "inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 text-[10px] font-medium",
        valuable
          ? "border-ember-400/70 bg-ember-600/15 text-parchment-50"
          : "border-ink-700 bg-ink-800 text-parchment-100/90",
        compact ? "uppercase" : "",
      ].join(" ")}
      title={titleParts.join(" · ")}
      data-testid="price-badge"
    >
      <span aria-hidden="true">◈</span>
      {typeof label === "string" ? (
        <span className="font-mono tabular-nums text-white/92">{label}</span>
      ) : (
        <span className="tabular-nums">{label}</span>
      )}
    </span>
  );
}
