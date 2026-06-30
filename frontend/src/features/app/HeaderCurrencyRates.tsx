import { useEffect, useState } from "react";

import { useCurrencyRates } from "@/api/hooks";

import { formatExChaosRate } from "./currencyRateDisplay";

function formatAgo(dataUpdatedAt: number, now: number): string {
  if (!dataUpdatedAt) return "";
  const s = Math.max(0, Math.floor((now - dataUpdatedAt) / 1000));
  if (s < 10) return "just now";
  if (s < 60) return `${s}s ago`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  const d = Math.floor(h / 24);
  if (d < 14) return `${d}d ago`;
  return new Date(dataUpdatedAt).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
  });
}

export interface HeaderCurrencyRatesProps {
  league: string | null;
}

/**
 * Cached league rates from React Query: div↔ex and ex→chaos (poe.ninja or server fallbacks).
 * Shown left of the league dropdown.
 */
export function HeaderCurrencyRates({ league }: HeaderCurrencyRatesProps) {
  const [now, setNow] = useState(() => Date.now());
  const q = useCurrencyRates(league);
  const r = q.data;
  const updated = q.dataUpdatedAt;

  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 30_000);
    return () => clearInterval(t);
  }, []);

  if (!league) return null;

  if (q.isLoading && !r) {
    return (
      <p
        className="min-w-0 text-[11px] text-ui-muted"
        aria-live="polite"
        aria-label="Loading currency rates"
      >
        <span className="font-mono">…</span>
      </p>
    );
  }

  if (q.isError || !r) {
    return null;
  }

  const cdiv = r.chaos_per_divine;
  const cex = r.chaos_per_exalted;
  const exPerDiv = r.exalted_per_divine ?? (cdiv > 0 && cex > 0 ? cdiv / cex : null);
  const exChaos = formatExChaosRate(cex);

  const line = (
    <>
      <span className="text-white/86">1 div</span>
      <span className="text-white/86"> ≈ </span>
      <span className="font-mono tabular-nums text-white/95">
        {exPerDiv != null ? Math.ceil(exPerDiv) : "—"}
      </span>
      <span className="text-white/86"> ex</span>
      <span className="text-white/55"> · </span>
      <span className="font-mono tabular-nums text-white/95">{exChaos.leftAmount}</span>
      <span className="text-white/86"> {exChaos.leftUnit}</span>
      <span className="text-white/86"> ≈ </span>
      <span className="font-mono tabular-nums text-white/95">{exChaos.rightAmount}</span>
      <span className="text-white/86"> {exChaos.rightUnit}</span>
    </>
  );

  return (
    <p
      className="min-w-0 text-[11px] leading-tight text-parchment-200/90"
      title={`Currency rates (cached). Source: ${r.source}. ${new Date(updated).toISOString()}`}
    >
      {line}
      {updated > 0 && (
        <span className="ml-1.5 text-ui-muted">({formatAgo(updated, now)})</span>
      )}
    </p>
  );
}
