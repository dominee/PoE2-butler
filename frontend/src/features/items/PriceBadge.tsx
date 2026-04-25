import type { PriceEstimate } from "@/api/types";
import { formatChaos } from "./itemMetrics";

export interface PriceBadgeProps {
  price: PriceEstimate | null | undefined;
  threshold?: number;
  compact?: boolean;
}

export function PriceBadge({ price, threshold, compact }: PriceBadgeProps) {
  if (!price) return null;
  const valuable = threshold != null && price.chaos_equiv >= threshold;
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
      <span>{formatChaos(price.chaos_equiv)}c</span>
    </span>
  );
}
