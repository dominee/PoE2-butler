import { useId, useMemo, useState, type ReactNode } from "react";

import type { CharacterDetail, EquipmentStatSummary, StatRow, StatSection } from "@/api/types";
import { PercentBar } from "@/features/items/PercentBar";
import { PANE_SECTION_HEADING } from "@/features/items/ItemModPresentation";

function formatNumber(n: number): string {
  if (n % 1 === 0) {
    return String(n);
  }
  return n.toFixed(1);
}

function formatRowValues(row: StatRow): string {
  const { label, values: vals } = row;
  if (vals.length === 0) {
    return "—";
  }
  const pct = label.includes("%");
  if (vals.length === 1) {
    const v = formatNumber(vals[0]!);
    return pct ? `${v}%` : v;
  }
  if (vals.length === 2) {
    return `${formatNumber(vals[0]!)} — ${formatNumber(vals[1]!)}` + (pct ? "%" : "");
  }
  return vals.map(formatNumber).join(" / ") + (pct ? "%" : "");
}

function sectionById(sections: StatSection[], id: string): StatSection | undefined {
  return sections.find((s) => s.id === id);
}

function findResourceRow(rows: StatRow[], kind: "life" | "mana" | "spirit"): StatRow | null {
  for (const r of rows) {
    const t = r.label;
    if (kind === "life" && /maximum life/i.test(t)) {
      return r;
    }
    if (kind === "mana" && /maximum mana/i.test(t)) {
      return r;
    }
    if (kind === "spirit" && (/\bto spirit\b/i.test(t) || /maximum spirit/i.test(t))) {
      return r;
    }
  }
  return null;
}

function findAttributeRow(rows: StatRow[], kind: "str" | "int" | "dex"): StatRow | null {
  for (const r of rows) {
    const t = r.label;
    if (kind === "str" && (/\bstrength\b| to str\b/i.test(t))) {
      return r;
    }
    if (kind === "dex" && (/\bdexterity\b| to dex\b/i.test(t))) {
      return r;
    }
    if (kind === "int" && (/\bintelligence\b| to int\b/i.test(t))) {
      return r;
    }
  }
  return null;
}

function findResistRow(
  rows: StatRow[],
  kind: "lightning" | "cold" | "fire" | "chaos" | "all",
): StatRow | null {
  for (const r of rows) {
    const t = r.label;
    if (kind === "all" && (/\ball elemental\b/i.test(t) || /\bto all element/i.test(t))) {
      return r;
    }
    if (!/resist/i.test(t)) {
      continue;
    }
    if (kind === "lightning" && /\blightning\b/i.test(t)) {
      return r;
    }
    if (kind === "cold" && /\bcold\b/i.test(t)) {
      return r;
    }
    if (kind === "fire" && /\bfire\b/i.test(t)) {
      return r;
    }
    if (kind === "chaos" && /\bchaos\b/i.test(t)) {
      return r;
    }
  }
  return null;
}

/** Flat pool stats only (skip “increased %”, suppression, block, etc.). */
function findDefenceRow(rows: StatRow[], kind: "es" | "armour" | "evasion"): StatRow | null {
  const skip = (low: string) =>
    /increased|more |less |suppression|block|ward|deflect|per accuracy|conversion|spell suppress|from evasion|from armour/i.test(
      low,
    );
  for (const r of rows) {
    const low = r.label.toLowerCase();
    if (skip(low)) {
      continue;
    }
    if (kind === "evasion" && /evasion rating/.test(low)) {
      return r;
    }
    if (kind === "armour" && /\barmou?r\b/.test(low) && !/%/.test(r.label)) {
      return r;
    }
    if (kind === "es" && /energy shield/.test(low)) {
      return r;
    }
  }
  if (kind === "es") {
    return (
      rows.find((r) => /energy shield/i.test(r.label.toLowerCase()) && !skip(r.label.toLowerCase())) ??
      null
    );
  }
  if (kind === "armour") {
    return (
      rows.find((r) => /\barmou?r\b/i.test(r.label) && !skip(r.label.toLowerCase())) ?? null
    );
  }
  return rows.find((r) => /evasion rating/i.test(r.label.toLowerCase())) ?? null;
}

function StatTextChip({ label, row }: { label: string; row: StatRow | null }) {
  return (
    <span className="inline-flex shrink-0 items-baseline gap-0.5" title={row?.label}>
      <span className="text-parchment-200/85">{label}</span>
      <span className="font-semibold tabular-nums text-white/92">
        {row ? formatRowValues(row) : "—"}
      </span>
    </span>
  );
}

function ResistChip({ row, icon, name }: { row: StatRow | null; icon: ReactNode; name: string }) {
  return (
    <span className="inline-flex shrink-0 items-center gap-0.5" title={row?.label ?? name}>
      <span className="sr-only">{name}</span>
      {icon}
      <span className="font-semibold tabular-nums text-white/92">
        {row ? formatRowValues(row) : "—"}
      </span>
    </span>
  );
}

function IconLightning() {
  return (
    <svg
      className="h-3.5 w-3.5 shrink-0 text-amber-300"
      viewBox="0 0 24 24"
      aria-hidden
    >
      <path
        d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"
        fill="currentColor"
      />
    </svg>
  );
}

function IconCold() {
  return (
    <svg
      className="h-3.5 w-3.5 shrink-0 text-sky-300"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      aria-hidden
    >
      <path d="M12 2v20M8 6l4-4 4 4M8 18l4 4 4-4M4 12h16M6 8l-4 4 4 4M18 8l4 4-4 4" />
    </svg>
  );
}

function IconFire() {
  return (
    <svg className="h-3.5 w-3.5 shrink-0 text-orange-400" viewBox="0 0 24 24" aria-hidden>
      <path
        fill="currentColor"
        d="M12 22c4-2 6-5 6-9 0-3-2-6-4-7 0 3-2 5-2 5s-2-2-2-5c-2 1-4 4-4 7 0 4 2 7 6 9z"
      />
    </svg>
  );
}

function IconChaos() {
  return (
    <svg
      className="h-3.5 w-3.5 shrink-0 text-violet-400"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      aria-hidden
    >
      <circle cx="12" cy="12" r="3" fill="currentColor" stroke="none" />
      <path d="M12 5v3M12 16v3M5 12h3M16 12h3M7 7l2 2M15 15l2 2M17 7l-2 2M9 15l-2 2" />
    </svg>
  );
}

function IconAllRes({ gradId }: { gradId: string }) {
  const href = `url(#${gradId})`;
  return (
    <svg className="h-3.5 w-3.5 shrink-0" viewBox="0 0 24 24" aria-hidden>
      <defs>
        <linearGradient id={gradId} x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#fbbf24" />
          <stop offset="35%" stopColor="#fb923c" />
          <stop offset="65%" stopColor="#7dd3fc" />
          <stop offset="100%" stopColor="#c4b5fd" />
        </linearGradient>
      </defs>
      <path
        d="M12 3 20 8 20 16 12 21 4 16 4 8 12 3z"
        fill="none"
        stroke={href}
        strokeWidth="1.5"
      />
    </svg>
  );
}

function useMandatoryBrief(sections: StatSection[]) {
  return useMemo(() => {
    const resSec = sectionById(sections, "resources");
    const attrSec = sectionById(sections, "attributes");
    const resistSec = sectionById(sections, "resistances");
    const defSec = sectionById(sections, "defences");

    const resRows = resSec?.rows ?? [];
    const attrRows = attrSec?.rows ?? [];
    const resistRows = resistSec?.rows ?? [];
    const defRows = defSec?.rows ?? [];

    return {
      life: findResourceRow(resRows, "life"),
      mana: findResourceRow(resRows, "mana"),
      spirit: findResourceRow(resRows, "spirit"),
      str: findAttributeRow(attrRows, "str"),
      int: findAttributeRow(attrRows, "int"),
      dex: findAttributeRow(attrRows, "dex"),
      resLightning: findResistRow(resistRows, "lightning"),
      resCold: findResistRow(resistRows, "cold"),
      resFire: findResistRow(resistRows, "fire"),
      resChaos: findResistRow(resistRows, "chaos"),
      resAll: findResistRow(resistRows, "all"),
      es: findDefenceRow(defRows, "es"),
      armour: findDefenceRow(defRows, "armour"),
      evasion: findDefenceRow(defRows, "evasion"),
    };
  }, [sections]);
}

export interface CharacterStatSummaryProps {
  detail: CharacterDetail;
}

/**
 * Cumulative equipment stats from the API. Collapsed: one compact strip of core stats.
 * Expanded: full per-section table.
 */
export function CharacterStatSummary({ detail }: CharacterStatSummaryProps) {
  const panelId = useId();
  const allResGradId = useId().replace(/:/g, "");
  const [expanded, setExpanded] = useState(false);
  const summary: EquipmentStatSummary = detail.stat_summary ?? { sections: [] };
  const sections = (summary.sections ?? []).filter((s) => s.rows.length > 0);

  const brief = useMandatoryBrief(sections);

  if (sections.length === 0) {
    return (
      <div className="panel border border-ink-700/80 bg-ink-900/40 px-3 py-2 text-xs text-parchment-200/80">
        No cumulative stats from equipment yet (all numeric mod lines are rolled up from equipped
        items, grouped by type).
      </div>
    );
  }

  return (
    <div
      className="panel border border-ink-700/80 bg-ink-900/40 px-3 py-2"
      aria-label="Equipment stat summary"
    >
      <div className="flex items-start justify-between gap-2">
        <h3 className={PANE_SECTION_HEADING}>Stat summary</h3>
        <button
          type="button"
          className="shrink-0 rounded border border-ink-600/80 bg-ink-950/50 px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-parchment-50/95 transition hover:border-ink-500 hover:bg-ink-900/80 focus:outline-none focus-visible:ring-2 focus-visible:ring-ember-400/60"
          aria-expanded={expanded}
          aria-controls={panelId}
          onClick={() => setExpanded((e) => !e)}
        >
          {expanded ? "Summary" : "All stats"}
        </button>
      </div>

      {!expanded && (
        <div
          className="mt-1.5 flex min-w-0 flex-nowrap items-center gap-x-2 overflow-x-auto pb-0.5 text-xs [-webkit-overflow-scrolling:touch]"
          data-testid="stat-summary-brief"
        >
          <div className="flex shrink-0 flex-nowrap items-center gap-x-2">
            <StatTextChip label="Life" row={brief.life} />
            <StatTextChip label="Mana" row={brief.mana} />
            <StatTextChip label="Spirit" row={brief.spirit} />
          </div>
          <div className="flex shrink-0 flex-nowrap items-center gap-x-2 border-l border-ink-600/50 pl-2">
            <StatTextChip label="Str" row={brief.str} />
            <StatTextChip label="Int" row={brief.int} />
            <StatTextChip label="Dex" row={brief.dex} />
          </div>
          <div className="flex shrink-0 flex-nowrap items-center gap-x-1.5 border-l border-ink-600/50 pl-2">
            <ResistChip row={brief.resLightning} name="Lightning resistance" icon={<IconLightning />} />
            <ResistChip row={brief.resCold} name="Cold resistance" icon={<IconCold />} />
            <ResistChip row={brief.resFire} name="Fire resistance" icon={<IconFire />} />
            <ResistChip row={brief.resChaos} name="Chaos resistance" icon={<IconChaos />} />
            <ResistChip
              row={brief.resAll}
              name="All elemental resistances"
              icon={<IconAllRes gradId={allResGradId} />}
            />
          </div>
          <div className="flex shrink-0 flex-nowrap items-center gap-x-2 border-l border-ink-600/50 pl-2">
            <StatTextChip label="ES" row={brief.es} />
            <StatTextChip label="Arm" row={brief.armour} />
            <StatTextChip label="Eva" row={brief.evasion} />
          </div>
        </div>
      )}

      {expanded && (
        <div id={panelId} className="mt-2 space-y-3 text-sm text-parchment-100/90" role="region">
          {sections.map((section) => (
            <div key={section.id}>
              <div className="flex items-center gap-2">
                <h4 className={PANE_SECTION_HEADING}>{section.label}</h4>
                {section.quality_pct != null && (
                  <div
                    className="flex min-w-0 flex-1 items-center gap-1.5"
                    title={`Section T1 quality: ${Math.round(section.quality_pct)}%`}
                  >
                    <PercentBar pct={section.quality_pct} size="sm" showValue />
                  </div>
                )}
              </div>
              <div className="mt-1 overflow-x-auto">
                <table className="w-full min-w-[12rem] border-separate border-spacing-0 text-left text-xs">
                  <tbody>
                    {section.rows.map((row, idx) => (
                      <tr
                        key={`${section.id}-${row.key}-${idx}`}
                        className="border-b border-ink-800/60 last:border-b-0"
                      >
                        <td className="pr-2 py-0.5 text-parchment-200/85">{row.label}</td>
                        <td className="w-[1%] whitespace-nowrap py-0.5 text-right font-semibold tabular-nums text-white/92">
                          {formatRowValues(row)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
