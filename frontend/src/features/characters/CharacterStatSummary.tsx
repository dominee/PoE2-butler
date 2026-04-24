import { useId, useMemo, useState } from "react";

import type { CharacterDetail, EquipmentStatSummary, StatRow, StatSection } from "@/api/types";

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

type BasicLine = { id: string; short: string; row: StatRow };

type BasicCategory = {
  id: string;
  label: string;
  lines: BasicLine[];
};

/** Order of “basic” groupings in the collapsed view. */
const BRIEF_CORE_ORDER = [
  "resources",
  "resistances",
  "attributes",
  "defences",
] as const;

const OTHER_BRIEF_MAX = 8;

function trimLabel(text: string, max = 34): string {
  if (text.length <= max) {
    return text;
  }
  return `${text.slice(0, max - 1)}…`;
}

function shortLabelForResourceRow(row: StatRow): string {
  const t = row.label;
  if (/maximum life/i.test(t)) {
    return "Life";
  }
  if (/maximum mana/i.test(t)) {
    return "Mana";
  }
  if (/\bto spirit\b|maximum spirit/i.test(t)) {
    return "Spirit";
  }
  return trimLabel(t, 32);
}

function shortLabelForResistRow(row: StatRow): string {
  const t = row.label;
  if (/\ball elemental\b/i.test(t) || /\bto all element/i.test(t)) {
    return "All res";
  }
  if (/\bchaos\b/i.test(t) && /resist/i.test(t)) {
    return "Chaos res";
  }
  if (/\bfire\b/i.test(t) && /resist/i.test(t)) {
    return "Fire res";
  }
  if (/\bcold\b/i.test(t) && /resist/i.test(t)) {
    return "Cold res";
  }
  if (/\blightning\b/i.test(t) && /resist/i.test(t)) {
    return "Lightn. res";
  }
  return trimLabel(t, 32);
}

function shortLabelForAttributeRow(row: StatRow): string {
  const t = row.label;
  if (/\bstrength\b| to str\b/i.test(t)) {
    return "Str";
  }
  if (/\bdexterity\b| to dex\b/i.test(t)) {
    return "Dex";
  }
  if (/\bintelligence\b| to int\b/i.test(t)) {
    return "Int";
  }
  return trimLabel(t, 32);
}

function shortLabelForDefenceRow(row: StatRow): string {
  return trimLabel(row.label, 32);
}

function linesForSection(
  kind: (typeof BRIEF_CORE_ORDER)[number],
  sec: StatSection
): BasicLine[] {
  return sec.rows.map((row, i) => {
    const short =
      kind === "resources"
        ? shortLabelForResourceRow(row)
        : kind === "resistances"
          ? shortLabelForResistRow(row)
          : kind === "attributes"
            ? shortLabelForAttributeRow(row)
            : shortLabelForDefenceRow(row);
    return { id: `${sec.id}-${row.key}-${i}`, short, row };
  });
}

/**
 * Grouped brief summary: every row in **resistances** and other core sections, with section labels
 * (same as API), plus a capped “other” group for the rest.
 */
function basicGroupedFromSections(sections: StatSection[]): BasicCategory[] {
  const byId = new Map(sections.map((s) => [s.id, s]));
  const out: BasicCategory[] = [];

  for (const sid of BRIEF_CORE_ORDER) {
    const sec = byId.get(sid);
    if (!sec?.rows.length) {
      continue;
    }
    out.push({ id: sid, label: sec.label, lines: linesForSection(sid, sec) });
  }

  const coreSet = new Set(BRIEF_CORE_ORDER as readonly string[]);
  const otherLines: BasicLine[] = [];
  for (const sec of sections) {
    if (coreSet.has(sec.id)) {
      continue;
    }
    sec.rows.forEach((row, i) => {
      if (otherLines.length >= OTHER_BRIEF_MAX) {
        return;
      }
      otherLines.push({
        id: `other-${sec.id}-${i}`,
        short: trimLabel(row.label, 32),
        row,
      });
    });
  }
  if (otherLines.length > 0) {
    out.push({ id: "other", label: "Other", lines: otherLines });
  }

  if (out.length > 0) {
    return out;
  }

  // Fallback: first few rows of any section, as a single block
  const any: BasicLine[] = [];
  for (const sec of sections) {
    for (const row of sec.rows) {
      if (any.length >= OTHER_BRIEF_MAX) {
        return [{ id: "fallback", label: "Summary", lines: any }];
      }
      any.push({
        id: `fb-${any.length}`,
        short: trimLabel(row.label, 32),
        row,
      });
    }
  }
  return [{ id: "fallback", label: "Summary", lines: any }];
}

export interface CharacterStatSummaryProps {
  detail: CharacterDetail;
}

/**
 * Cumulative equipment stats from the API. Collapsed: basic categories. Expanded: full table.
 */
export function CharacterStatSummary({ detail }: CharacterStatSummaryProps) {
  const panelId = useId();
  const [expanded, setExpanded] = useState(false);
  const summary: EquipmentStatSummary = detail.stat_summary ?? { sections: [] };
  const sections = (summary.sections ?? []).filter((s) => s.rows.length > 0);

  const briefGroups = useMemo(() => basicGroupedFromSections(sections), [sections]);

  if (sections.length === 0) {
    return (
      <div className="panel border border-ink-700/80 bg-ink-900/40 px-3 py-2 text-xs text-ink-500">
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
        <h3 className="text-[10px] font-semibold uppercase tracking-widest text-ink-500">
          Stat summary
        </h3>
        <button
          type="button"
          className="shrink-0 rounded border border-ink-600/80 bg-ink-950/50 px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-parchment-200/90 transition hover:border-ink-500 hover:bg-ink-900/80"
          aria-expanded={expanded}
          aria-controls={panelId}
          onClick={() => setExpanded((e) => !e)}
        >
          {expanded ? "Summary" : "All stats"}
        </button>
      </div>

      {!expanded && (
        <div
          className="mt-2 space-y-2.5 text-sm text-parchment-100/90"
          data-testid="stat-summary-brief"
        >
          {briefGroups.map((cat) => (
            <section key={cat.id} aria-label={cat.label}>
              <h4 className="text-[9px] font-medium uppercase tracking-wide text-ink-500">
                {cat.label}
              </h4>
              <ul className="mt-0.5 flex flex-wrap gap-x-3 gap-y-1 text-xs">
                {cat.lines.map((b) => (
                  <li
                    key={b.id}
                    className="inline-flex min-w-0 max-w-full items-baseline gap-1.5"
                  >
                    <span className="shrink-0 text-ink-500">{b.short}</span>
                    <span className="font-semibold tabular-nums text-ember-200/90">
                      {formatRowValues(b.row)}
                    </span>
                  </li>
                ))}
              </ul>
            </section>
          ))}
        </div>
      )}

      {expanded && (
        <div id={panelId} className="mt-2 space-y-3 text-sm text-parchment-100/90" role="region">
          {sections.map((section) => (
            <div key={section.id}>
              <h4 className="text-[10px] font-medium uppercase tracking-wide text-ink-500">
                {section.label}
              </h4>
              <div className="mt-1 overflow-x-auto">
                <table className="w-full min-w-[12rem] border-separate border-spacing-0 text-left text-xs">
                  <tbody>
                    {section.rows.map((row, idx) => (
                      <tr
                        key={`${section.id}-${row.key}-${idx}`}
                        className="border-b border-ink-800/60 last:border-b-0"
                      >
                        <td className="pr-2 py-0.5 text-ink-400">{row.label}</td>
                        <td className="w-[1%] whitespace-nowrap py-0.5 text-right font-semibold tabular-nums text-ember-200/90">
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
