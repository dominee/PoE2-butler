/**
 * Roll-quality / T1-percentage bar.
 *
 * Shows a horizontal bar that fills from 0 to `pct` (capped visually at 110%).
 * A tick mark at 100 % indicates the T1 maximum so overcapped values are
 * obvious.
 *
 * Colour scale:
 *  ≥ 100 %  gold  (overcapped / perfect)
 *   90-99%  amber
 *   70-89%  green
 *   50-69%  yellow
 *    < 50%  grey
 *   null    dark (unknown — no mod data available)
 */

const VISUAL_MAX = 110; // bar width represents 0 – 110 %

function barColor(pct: number): string {
  if (pct >= 100) return "bg-amber-400";
  if (pct >= 90)  return "bg-yellow-400";
  if (pct >= 70)  return "bg-lime-500";
  if (pct >= 50)  return "bg-sky-500";
  return "bg-ink-500";
}

export interface PercentBarProps {
  /** Percentage value (0-100+). Null = unknown / no data. */
  pct: number | null;
  /** Tier label, e.g. "T2" — shown in the tooltip. */
  tierLabel?: string;
  /** Whether to show the numeric percentage next to the bar. */
  showValue?: boolean;
}

export function PercentBar({ pct, tierLabel, showValue = true }: PercentBarProps) {
  if (pct == null) {
    return (
      <div className="flex items-center gap-1.5">
        <div className="h-1.5 flex-1 rounded-full bg-ink-700" title="No tier data available" />
        {showValue && <span className="w-8 text-right text-[10px] text-ink-600">—</span>}
      </div>
    );
  }

  const clampedPct = Math.min(pct, VISUAL_MAX);
  const widthPct = (clampedPct / VISUAL_MAX) * 100;
  const color = barColor(pct);
  const label = tierLabel ? `${tierLabel}: ${pct}%` : `${pct}%`;

  return (
    <div className="flex items-center gap-1.5" title={label}>
      {/* Track */}
      <div className="relative h-1.5 flex-1 overflow-visible rounded-full bg-ink-700">
        {/* Fill */}
        <div
          className={`absolute inset-y-0 left-0 rounded-full transition-all ${color}`}
          style={{ width: `${widthPct}%` }}
        />
        {/* T1-max tick at the 100 % position (= 100/110 of track width) */}
        <div
          className="absolute inset-y-[-2px] w-px bg-parchment-200/30"
          style={{ left: `${(100 / VISUAL_MAX) * 100}%` }}
          title="T1 maximum"
        />
      </div>
      {showValue && (
        <span
          className={`w-8 text-right text-[10px] font-semibold tabular-nums ${pct >= 100 ? "text-amber-400" : "text-ink-400"}`}
        >
          {pct}%
        </span>
      )}
    </div>
  );
}

/** Compute item score as the mean of available mod percentages. */
export function computeItemScore(pcts: (number | null)[]): number | null {
  const valid = pcts.filter((p): p is number => p != null);
  if (valid.length === 0) return null;
  return Math.round(valid.reduce((a, b) => a + b, 0) / valid.length);
}
