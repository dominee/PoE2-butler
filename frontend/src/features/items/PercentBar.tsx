/**
 * Roll-quality / T1-percentage bar.
 *
 * Fills from 0 to `pct` (capped visually at 110 %). A tick at 100 % marks the T1 cap.
 * Fill uses a two-stop theme gradient (ink → ember); value text uses the same pair.
 */

const VISUAL_MAX = 110;

/** Bar fill: muted ink at low roll, ember accent at high roll (gradient spans the filled width). */
const FILL_GRADIENT = "bg-gradient-to-r from-ink-600 to-ember-400";

function valueTextClass(pct: number, variant: PercentBarProps["variant"]): string {
  const strong = variant === "t1" && pct >= 100 ? true : pct >= 92;
  return strong ? "text-ember-400" : "text-ink-400";
}

export interface PercentBarProps {
  /** Percentage value (0–100+). Null = unknown / no data. */
  pct: number | null;
  /** Shown in the title tooltip. */
  tierLabel?: string;
  showValue?: boolean;
  /** Kept for semantics / future tuning; fill is always the same theme gradient. */
  variant?: "default" | "withinTier" | "t1";
  /** Slightly taller for the item detail pane. */
  size?: "sm" | "md";
}

export function PercentBar({
  pct,
  tierLabel,
  showValue = true,
  variant = "default",
  size = "sm",
}: PercentBarProps) {
  const h = size === "md" ? "h-2" : "h-1.5";
  if (pct == null) {
    return (
      <div className="flex min-w-0 items-center gap-1.5">
        <div
          className={`${h} min-w-0 flex-1 rounded-full bg-ink-700/90`}
          title="No roll data for this line"
        />
        {showValue && (
          <span className="w-9 shrink-0 text-right text-[10px] text-ink-600">—</span>
        )}
      </div>
    );
  }

  const clampedPct = Math.min(pct, VISUAL_MAX);
  const widthPct = (clampedPct / VISUAL_MAX) * 100;
  const label = tierLabel ? `${tierLabel}: ${pct}%` : `${pct}%`;
  const valueClass = valueTextClass(pct, variant);

  return (
    <div className="flex min-w-0 items-center gap-1.5" title={label}>
      <div className={`relative ${h} min-w-0 flex-1 overflow-visible rounded-full bg-ink-800/90`}>
        <div
          className={`absolute inset-y-0 left-0 rounded-full transition-[width] ${FILL_GRADIENT}`}
          style={{ width: `${widthPct}%` }}
        />
        <div
          className="absolute inset-y-[-2px] w-px bg-ember-400/35"
          style={{ left: `${(100 / VISUAL_MAX) * 100}%` }}
          title="100% on this scale = T1 max"
        />
      </div>
      {showValue && (
        <span className={`w-9 shrink-0 text-right text-[10px] font-semibold tabular-nums ${valueClass}`}>
          {pct}%
        </span>
      )}
    </div>
  );
}
