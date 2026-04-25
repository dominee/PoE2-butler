/**
 * Roll-quality / T1-percentage bar.
 *
 * Fills from 0 to `pct` (capped visually at 110 %). A tick at 100 % marks the T1 cap.
 * Variants tint the fill for “within this affix tier” vs “vs global T1 max”.
 */

const VISUAL_MAX = 110;

function barColor(pct: number, variant: PercentBarProps["variant"]): string {
  if (variant === "withinTier") {
    if (pct >= 90) {
      return "bg-cyan-400";
    }
    if (pct >= 70) {
      return "bg-sky-500";
    }
    if (pct >= 50) {
      return "bg-slate-500";
    }
    return "bg-ink-500";
  }
  if (variant === "t1") {
    if (pct >= 100) {
      return "bg-amber-400";
    }
    if (pct >= 90) {
      return "bg-yellow-500";
    }
    if (pct >= 70) {
      return "bg-lime-500";
    }
    if (pct >= 50) {
      return "bg-sky-500/80";
    }
    return "bg-ink-500";
  }
  if (pct >= 100) {
    return "bg-amber-400";
  }
  if (pct >= 90) {
    return "bg-yellow-400";
  }
  if (pct >= 70) {
    return "bg-lime-500";
  }
  if (pct >= 50) {
    return "bg-sky-500";
  }
  return "bg-ink-500";
}

export interface PercentBarProps {
  /** Percentage value (0–100+). Null = unknown / no data. */
  pct: number | null;
  /** Shown in the title tooltip. */
  tierLabel?: string;
  showValue?: boolean;
  /** `withinTier` = cyan-forward; `t1` = gold T1 ladder; `default` = mixed (legacy). */
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
  const color = barColor(pct, variant);
  const label = tierLabel ? `${tierLabel}: ${pct}%` : `${pct}%`;

  const valueClass =
    variant === "t1" && pct >= 100
      ? "text-amber-400"
      : variant === "withinTier" && pct >= 90
        ? "text-cyan-300/90"
        : "text-ink-300";

  return (
    <div className="flex min-w-0 items-center gap-1.5" title={label}>
      <div className={`relative ${h} min-w-0 flex-1 overflow-visible rounded-full bg-ink-800/90`}>
        <div
          className={`absolute inset-y-0 left-0 rounded-full transition-all ${color}`}
          style={{ width: `${widthPct}%` }}
        />
        <div
          className="absolute inset-y-[-2px] w-px bg-amber-200/25"
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
