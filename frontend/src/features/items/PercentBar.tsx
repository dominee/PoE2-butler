/**
 * Roll-quality / T1-percentage bar — two rendering modes:
 *
 * **Fill mode** (default): fills from 0 to `pct` (capped visually at 110 %).
 * A cap tick at 100 % marks T1 max.
 *
 * **Candle mode** (when `bandMin` and `bandMax` are supplied): the track is the
 * full 0–110 % scale; a semi-transparent band overlays the current tier's
 * [bandMin, bandMax] range; a bright tick marks the actual roll position.
 * Tier boundary markers (T2, T3 …) are shown in both modes.
 */

const VISUAL_MAX = 110;

/** Bar fill: muted ink at low roll, ember accent at high roll (gradient spans the filled width). */
const FILL_GRADIENT = "bg-gradient-to-r from-ink-600 to-ember-400";

function valueTextClass(pct: number, variant: PercentBarProps["variant"]): string {
  const strong = variant === "t1" && pct >= 100 ? true : pct >= 92;
  return strong ? "text-ember-400" : "text-ui-caption";
}

/** Convert a raw percentage to a CSS `left` offset on the bar. */
function toBarPct(p: number): number {
  return (Math.min(p, VISUAL_MAX) / VISUAL_MAX) * 100;
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
  /**
   * Tier boundary positions as % of T1 max (T2 max, T3 max, …).
   * Drawn as subtle vertical ticks on the track.
   * Computed by `tierBoundaryPcts()` in modRollMetrics.
   */
  tierMarkers?: number[];
  /**
   * Left edge of the current tier's range, as % of T1 max.
   * When supplied together with `bandMax`, switches to **candle mode**.
   */
  bandMin?: number | null;
  /**
   * Right edge of the current tier's range, as % of T1 max.
   * When supplied together with `bandMin`, switches to **candle mode**.
   */
  bandMax?: number | null;
}

export function PercentBar({
  pct,
  tierLabel,
  showValue = true,
  variant = "default",
  size = "sm",
  tierMarkers,
  bandMin,
  bandMax,
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
          <span className="w-9 shrink-0 text-right text-[10px] text-ui-muted">—</span>
        )}
      </div>
    );
  }

  const label = tierLabel ? `${tierLabel}: ${pct}%` : `${pct}%`;
  const valueClass = valueTextClass(pct, variant);

  const isCandle = bandMin != null && bandMax != null;

  // ── Candle mode ────────────────────────────────────────────────────────────
  if (isCandle) {
    const bandLeftPct = toBarPct(bandMin!);
    const bandRightPct = toBarPct(bandMax!);
    const bandWidthPct = Math.max(0, bandRightPct - bandLeftPct);
    const tickPct = toBarPct(pct);

    return (
      <div className="flex min-w-0 items-center gap-1.5" title={label}>
        <div className={`relative ${h} min-w-0 flex-1 overflow-visible rounded-full bg-ink-800/90`}>
          {/* Tier range band (candle body) */}
          <div
            className="absolute inset-y-0 rounded-sm bg-ink-500/50"
            style={{ left: `${bandLeftPct}%`, width: `${bandWidthPct}%` }}
            title={`Tier range: ${Math.round(bandMin!)}%–${Math.round(bandMax!)}% of T1`}
          />
          {/* Tier boundary markers (T2 max, T3 max, …) */}
          {tierMarkers?.map((p, i) => (
            <div
              key={i}
              className="absolute inset-y-0 w-px bg-ink-400/45"
              style={{ left: `${toBarPct(p)}%` }}
              title={`T${i + 2} max: ${p}%`}
            />
          ))}
          {/* T1 cap tick */}
          <div
            className="absolute inset-y-[-2px] w-px bg-ember-400/35"
            style={{ left: `${toBarPct(100)}%` }}
            title="T1 max (100%)"
          />
          {/* Actual roll tick — slightly wider and brighter */}
          <div
            className="absolute inset-y-[-2px] w-0.5 rounded-sm bg-ember-400"
            style={{ left: `${tickPct}%` }}
            title={`Roll: ${pct}% of T1 max`}
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

  // ── Fill mode (no band data) ───────────────────────────────────────────────
  const clampedPct = Math.min(pct, VISUAL_MAX);
  const widthPct = (clampedPct / VISUAL_MAX) * 100;

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
        {tierMarkers?.map((p, i) => (
          <div
            key={i}
            className="absolute inset-y-0 w-px bg-ink-400/55"
            style={{ left: `${toBarPct(p)}%` }}
            title={`T${i + 2} max: ${p}%`}
          />
        ))}
      </div>
      {showValue && (
        <span className={`w-9 shrink-0 text-right text-[10px] font-semibold tabular-nums ${valueClass}`}>
          {pct}%
        </span>
      )}
    </div>
  );
}
