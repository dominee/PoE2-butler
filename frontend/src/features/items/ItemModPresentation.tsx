/**
 * Shared mod / tier UI used by the item detail pane and PNG export.
 */

import type { ModDetail } from "@/api/types";
import { parseModParts } from "@/utils/modText";

import { PercentBar } from "./PercentBar";

// ── tier badge ──────────────────────────────────────────────────────────────

function tierBadgeClass(tier: number): string {
  if (tier === 1) return "bg-amber-500/25 text-amber-300 border-amber-500/50";
  if (tier === 2) return "bg-yellow-600/20 text-yellow-300 border-yellow-500/40";
  if (tier <= 4) return "bg-lime-900/25 text-lime-400/80 border-lime-700/40";
  if (tier <= 6) return "bg-ink-600/60 text-ink-300 border-ink-500";
  return "bg-ink-700/60 text-ink-500 border-ink-600";
}

function TierBadge({ tier }: { tier: number }) {
  return (
    <span
      className={`inline-flex shrink-0 items-center rounded border px-1 py-px text-[9px] font-bold leading-none ${tierBadgeClass(tier)}`}
      title={`Tier ${tier}`}
    >
      T{tier}
    </span>
  );
}

// ── mod text ────────────────────────────────────────────────────────────────

/** Render a mod string with numeric values highlighted in parchment-50. */
export function ModText({ raw }: { raw: string }) {
  const parts = parseModParts(raw);
  return (
    <span>
      {parts.map((part, i) =>
        part.isNum ? (
          // eslint-disable-next-line react/no-array-index-key
          <strong key={i} className="font-semibold text-parchment-50">
            {part.text}
          </strong>
        ) : (
          // eslint-disable-next-line react/no-array-index-key
          <span key={i}>{part.text}</span>
        ),
      )}
    </span>
  );
}

function extractModValue(modText: string): number | null {
  const parts = parseModParts(modText);
  const numPart = parts.find((p) => p.isNum);
  if (!numPart) return null;
  const n = parseFloat(numPart.text.replace("%", ""));
  return Number.isFinite(n) ? Math.abs(n) : null;
}

function rollQuality(value: number, min: number, max: number): number {
  if (max <= min) return 100;
  return Math.round(((value - min) / (max - min)) * 100);
}

export function modQuality(mod: string, detail: ModDetail | undefined): number | null {
  const mag = detail?.magnitudes?.[0];
  if (!mag) return null;
  const value = extractModValue(mod);
  if (value == null) return null;

  if (mag.t1_max != null && mag.t1_max > 0) {
    return Math.round((value / mag.t1_max) * 100);
  }

  if (mag.min == null || mag.max == null) return null;
  return rollQuality(value, mag.min, mag.max);
}

/**
 * Renders one explicit mod line with an optional tier badge, roll range, and
 * quality bar.
 */
export function ExplicitModLine({
  mod,
  detail,
}: {
  mod: string;
  detail: ModDetail | undefined;
}) {
  const tier = detail?.tier ?? null;
  const mag = detail?.magnitudes?.[0];
  const hasRange = mag?.min != null && mag?.max != null && mag.min !== mag.max;
  const hasCrossTier = mag?.t1_max != null;
  const pct = modQuality(mod, detail);

  return (
    <li className="break-words leading-snug">
      <div className="flex items-start gap-1.5">
        {tier != null && <TierBadge tier={tier} />}
        <span className="min-w-0 flex-1">
          <ModText raw={mod} />
          {hasRange && (
            <span className="ml-1 text-[10px] text-ink-500">
              [{mag!.min}–{mag!.max}]
            </span>
          )}
          {hasCrossTier && (
            <span className="ml-1 text-[10px] text-parchment-100/40">T1 max: {mag!.t1_max}</span>
          )}
        </span>
      </div>
      {detail != null && (
        <PercentBar
          pct={pct}
          tierLabel={
            hasCrossTier
              ? `vs T1 max (${mag!.t1_max})`
              : tier != null
                ? `T${tier} roll quality`
                : undefined
          }
          showValue={pct != null}
        />
      )}
    </li>
  );
}

export function ModSection({ title, mods, tone }: { title: string; mods: string[]; tone: string }) {
  if (mods.length === 0) return null;
  return (
    <div>
      <h4 className="text-[10px] font-semibold uppercase tracking-widest text-ink-500">
        {title}
      </h4>
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
  return <div className="my-0.5 border-t border-ink-600/50" />;
}
