/**
 * Shared mod / tier UI used by the item detail pane and PNG export.
 */

import type { ModDetail } from "@/api/types";
import { parseModParts } from "@/utils/modText";

import { computeModRollMetrics } from "./modRollMetrics";
import { modTextRangeHint } from "./modTextRange";
import { PercentBar } from "./PercentBar";

export { modQuality, computeModRollMetrics, itemRollScoreState } from "./modRollMetrics";

// ── tier badge ──────────────────────────────────────────────────────────────

function tierBadgeClass(tier: number): string {
  if (tier === 1) {
    return "bg-amber-500/30 text-amber-200 border-amber-400/50 shadow-[0_0_6px_rgba(245,158,11,0.2)]";
  }
  if (tier === 2) {
    return "bg-yellow-600/25 text-yellow-200 border-yellow-500/45";
  }
  if (tier <= 4) {
    return "bg-lime-900/30 text-lime-300/90 border-lime-600/40";
  }
  if (tier <= 6) {
    return "bg-ink-600/60 text-ink-300 border-ink-500";
  }
  return "bg-ink-700/60 text-ink-500 border-ink-600";
}

function TierBadge({ tier }: { tier: number }) {
  return (
    <span
      className={`inline-flex shrink-0 items-center rounded border px-1 py-px text-[9px] font-bold leading-none ${tierBadgeClass(tier)}`}
      title={`Affix tier ${tier} (1 = best)`}
    >
      T{tier}
    </span>
  );
}

// ── mod text ────────────────────────────────────────────────────────────────

/** Render a mod string with numeric values highlighted. */
export function ModText({ raw }: { raw: string }) {
  const parts = parseModParts(raw);
  return (
    <span>
      {parts.map((part, i) =>
        part.isNum ? (
          // eslint-disable-next-line react/no-array-index-key
          <strong key={i} className="font-semibold text-parchment-100">
            {part.text}
          </strong>
        ) : (
          // eslint-disable-next-line react/no-array-index-key
          <span key={i} className="text-parchment-200/95">
            {part.text}
          </span>
        ),
      )}
    </span>
  );
}

// ── explicit (and detailed implicit) line ─────────────────────────────────

/**
 * One mod line: tier chip, GGG string, range/T1 hints, and up to two roll bars
 * (within this affix’s tier range vs % of T1 max).
 */
export function ExplicitModLine({ mod, detail }: { mod: string; detail: ModDetail | undefined }) {
  const tier = detail?.tier ?? null;
  const mag = detail?.magnitudes?.[0];
  const m = computeModRollMetrics(mod, detail);
  const hasGggRange = mag?.min != null && mag?.max != null;
  const fromModText = !hasGggRange ? modTextRangeHint(mod) : null;
  const showBars = m.withinTierPct != null || m.vsT1Pct != null;
  const showMetaRow = hasGggRange || fromModText != null;
  const showUnderline = tier != null || showMetaRow || showBars;

  return (
    <li className="break-words leading-snug">
      <div
        className={`flex items-start gap-1.5 pb-1.5 pl-0.5 ${
          showUnderline ? "border-b border-ink-800/40" : ""
        }`}
      >
        {tier != null && <TierBadge tier={tier} />}
        <div className="min-w-0 flex-1">
          <div className="text-[13px] leading-relaxed tracking-[0.01em] text-parchment-100/95">
            <ModText raw={mod} />
          </div>
          {hasGggRange && (
            <div className="mt-0.5 text-[10px] text-ink-500">
              <span className="text-ink-500">This affix band: </span>
              <span className="font-mono text-amber-200/90">
                {mag!.min} – {mag!.max}
                {mag!.min === mag!.max ? " (fixed in tier)" : ""}
              </span>
              {m.hasT1 && mag?.t1_max != null && (
                <span className="ml-2 text-ink-500">
                  T1 cap: <span className="font-mono text-amber-300/70">{mag.t1_max}</span>
                </span>
              )}
            </div>
          )}
          {!hasGggRange && fromModText && (
            <div className="mt-0.5 text-[10px] text-ink-500">
              <span className="text-ink-500">Rolled values: </span>
              <span className="font-mono text-amber-200/85">{fromModText}</span>
            </div>
          )}
        </div>
      </div>
      {showBars && (
        <div className="mt-1.5 space-y-1.5 pl-0.5">
          {m.withinTierPct != null && m.hasTierRange && (
            <div className="flex items-center gap-2 text-[10px]">
              <span className="w-20 shrink-0 text-ink-500">Tier roll</span>
              <div className="min-w-0 flex-1">
                <PercentBar
                  variant="withinTier"
                  size="md"
                  pct={m.withinTierPct}
                  tierLabel="Within this affix band"
                />
              </div>
            </div>
          )}
          {m.vsT1Pct != null && (
            <div className="flex items-center gap-2 text-[10px]">
              <span className="w-20 shrink-0 text-ink-500">vs T1</span>
              <div className="min-w-0 flex-1">
                <PercentBar
                  variant="t1"
                  size="md"
                  pct={m.vsT1Pct}
                  tierLabel="Compared to best tier value"
                />
              </div>
            </div>
          )}
        </div>
      )}
    </li>
  );
}

export function ModSection({ title, mods, tone }: { title: string; mods: string[]; tone: string }) {
  if (mods.length === 0) {
    return null;
  }
  return (
    <div>
      <h4 className="text-[10px] font-semibold uppercase tracking-widest text-ink-500">{title}</h4>
      <ul className={`mt-1 space-y-0.5 text-sm ${tone}`}>
        {mods.map((mod, idx) => (
          // eslint-disable-next-line react/no-array-index-key
          <li key={idx} className="break-words leading-snug">
            <ModText raw={mod} />
          </li>
        ))}
      </ul>
    </div>
  );
}

export function ModDivider() {
  return <div className="my-1 border-t border-amber-950/20" />;
}
