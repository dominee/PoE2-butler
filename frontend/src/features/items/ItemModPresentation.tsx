/**
 * Shared mod / tier UI used by the item detail pane and PNG export.
 */

import type { ModDetail } from "@/api/types";
import { parseModParts } from "@/utils/modText";

import { computeModRollMetrics, tierBoundaryPcts } from "./modRollMetrics";
import { modTextRangeHint } from "./modTextRange";
import { PercentBar } from "./PercentBar";

/** Uppercase pane section titles (Stats, Prefixes, Public link, …). */
export const PANE_SECTION_HEADING =
  "text-[10px] font-semibold uppercase tracking-widest text-parchment-50/95";

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

function TierBadge({ tier, totalTiers }: { tier: number; totalTiers?: number | null }) {
  const label = totalTiers != null ? `T${tier}/${totalTiers}` : `T${tier}`;
  const title =
    totalTiers != null
      ? `Affix tier ${tier} of ${totalTiers} (T1 = best, T${totalTiers} = lowest)`
      : `Affix tier ${tier} (1 = best)`;
  return (
    <span
      className={`inline-flex shrink-0 items-center rounded border px-1 py-px text-[9px] font-bold leading-none ${tierBadgeClass(tier)}`}
      title={title}
    >
      {label}
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
          <strong key={i} className="font-semibold tabular-nums text-white/92">
            {part.text}
          </strong>
        ) : (
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
 *
 * For uniques, set ``showRollHints={false}``: GGG magnitudes / regex on mod text
 * are often a poor match for the item’s possible rolls.
 */
export function ExplicitModLine({
  mod,
  detail,
  showRollHints = true,
  /** Wiki-style type range for this mod line, shown right-aligned (uniques with bundled data). */
  referenceRangeText,
  /**
   * 0–100: roll position in the type range (wiki); shown when reference data and a parseable value
   * exist. Mutually independent from GGG tier / T1 bars.
   */
  typeRollPercent,
}: {
  mod: string;
  detail: ModDetail | undefined;
  showRollHints?: boolean;
  referenceRangeText?: string | null;
  typeRollPercent?: number | null;
}) {
  const tier = detail?.tier ?? null;
  const totalTiers = detail?.all_tiers?.length ?? null;
  const mag = detail?.magnitudes?.[0];
  const m = showRollHints ? computeModRollMetrics(mod, detail) : null;
  const t1Max = mag?.t1_max ?? null;
  const tierMarkers =
    showRollHints && t1Max != null ? tierBoundaryPcts(detail, t1Max) : [];
  const hasGggRange = showRollHints && mag?.min != null && mag?.max != null;
  const fromModText =
    showRollHints && !hasGggRange ? modTextRangeHint(mod) : null;
  const showBars =
    showRollHints && (m?.withinTierPct != null || m?.vsT1Pct != null);
  const showRefCol = Boolean(referenceRangeText?.trim());
  const showTypeQuality = typeRollPercent != null;
  const showMetaRow = hasGggRange || fromModText != null;
  const showUnderline =
    tier != null || showMetaRow || showBars || showRefCol || showTypeQuality;

  return (
    <li className="break-words leading-snug">
      <div
        className={`flex items-start gap-1.5 pb-1.5 pl-0.5 ${
          showUnderline ? "border-b border-ink-800/40" : ""
        }`}
      >
        {tier != null && <TierBadge tier={tier} totalTiers={totalTiers} />}
        <div className="min-w-0 flex-1">
          <div
            className={`flex w-full min-w-0 items-baseline gap-3 ${
              referenceRangeText?.trim() ? "justify-between" : ""
            }`}
          >
            <div className="min-w-0 flex-1 text-[13px] leading-relaxed tracking-[0.01em] text-parchment-100/95">
              <ModText raw={mod} />
            </div>
            {referenceRangeText?.trim() ? (
              <span
                className="shrink-0 whitespace-nowrap text-right font-mono text-[11px] text-parchment-200/85 tabular-nums"
                title="Community-sourced type roll range (not a snapshot of this one item)"
              >
                {referenceRangeText.trim()}
              </span>
            ) : null}
          </div>
          {hasGggRange && (
            <div className="mt-0.5 text-[10px] text-parchment-100/80">
              <span className="text-parchment-200/90">This affix band: </span>
              <span className="font-mono text-amber-200/90">
                {mag!.min} – {mag!.max}
                {mag!.min === mag!.max ? " (fixed in tier)" : ""}
              </span>
              {m?.hasT1 && mag?.t1_max != null && (
                <span className="ml-2 text-parchment-200/85">
                  T1 cap: <span className="font-mono text-amber-300/70">{mag.t1_max}</span>
                </span>
              )}
              {tier != null && detail?.all_tiers != null && (() => {
                const currentTier = detail.all_tiers.find((t) => t.tier_ggg === tier);
                return currentTier ? (
                  <span className="ml-2 text-parchment-200/70">
                    ilvl {currentTier.required_level}+
                  </span>
                ) : null;
              })()}
            </div>
          )}
          {!hasGggRange && fromModText && (
            <div className="mt-0.5 text-[10px] text-parchment-100/80">
              <span className="text-parchment-200/90">Rolled values: </span>
              <span className="font-mono text-amber-200/85">{fromModText}</span>
            </div>
          )}
        </div>
      </div>
      {showTypeQuality && typeRollPercent != null && (
        <div className="mt-1.5 pl-0.5">
          <div className="flex items-center gap-2 text-[10px]">
            <span
              className="w-20 shrink-0 text-parchment-200/90"
              title="How close this roll is to the best end of the wiki / type range for this mod"
            >
              Type quality
            </span>
            <div className="min-w-0 flex-1">
              <PercentBar
                size="md"
                pct={typeRollPercent}
                showValue
                variant="default"
                tierLabel="0% = type min, 100% = best in wiki range; reduced = lower is better"
              />
            </div>
          </div>
        </div>
      )}
      {showBars && m && (
        <div className="mt-1.5 pl-0.5">
          <div className="flex items-center gap-2 text-[10px]">
            <span className="w-20 shrink-0 text-parchment-200/90">Roll</span>
            <div className="min-w-0 flex-1">
              <PercentBar
                variant="t1"
                size="md"
                pct={m.vsT1Pct ?? m.withinTierPct}
                tierLabel={
                  m.vsT1Pct != null
                    ? "Band = tier range · tick = your roll · scale = T1 max"
                    : "Roll position within this tier's range"
                }
                bandMin={m.bandMinPct}
                bandMax={m.bandMaxPct}
                tierMarkers={tierMarkers}
              />
            </div>
          </div>
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
      <h4 className={PANE_SECTION_HEADING}>{title}</h4>
      <ul className={`mt-1 space-y-0.5 text-sm ${tone}`}>
        {mods.map((mod, idx) => (
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
