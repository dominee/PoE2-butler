import { useCurrencyRates } from "@/api/hooks";

export interface CurrencyExchangeHintProps {
  league: string | null;
  className?: string;
}

/** Compact league div↔ex line when economy API data is available. */
export function CurrencyExchangeHint({ league, className = "" }: CurrencyExchangeHintProps) {
  const q = useCurrencyRates(league);
  const r = q.data;
  if (!r?.exalted_per_divine || r.exalted_per_divine <= 0) return null;
  return (
    <p
      className={`text-[11px] text-ink-500 ${className}`.trim()}
      title="From community economy data (poe.ninja or configured fallbacks) for this league"
    >
      <span className="text-ink-600">1 Divine ≈ </span>
      <span className="font-mono tabular-nums text-parchment-200/90">
        {r.exalted_per_divine.toFixed(1)}
      </span>
      <span className="text-ink-600"> Exalted</span>
    </p>
  );
}
