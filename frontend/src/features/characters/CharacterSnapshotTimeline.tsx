import { useMemo, useState } from "react";

import { useCharacterSnapshots } from "@/api/hooks";
import type { CharacterSnapshotChange, CharacterSnapshotMeta } from "@/api/types";

export type SnapshotSelection = number | "current";

export interface CharacterSnapshotTimelineProps {
  characterName: string;
  selectedId: SnapshotSelection;
  onSelect: (id: SnapshotSelection) => void;
}

function formatSnapshotDate(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
  });
}

function formatSnapshotTime(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleTimeString(undefined, {
    hour: "2-digit",
    minute: "2-digit",
  });
}

function changePrefix(kind: CharacterSnapshotChange["kind"]): string {
  if (kind === "new") return "+";
  if (kind === "removed") return "−";
  return "~";
}

function isSelected(snap: CharacterSnapshotMeta, selectedId: SnapshotSelection): boolean {
  if (snap.is_current) return selectedId === "current";
  return selectedId === snap.id;
}

function selectionLabel(snap: CharacterSnapshotMeta): string {
  const when = `${formatSnapshotDate(snap.fetched_at)} ${formatSnapshotTime(snap.fetched_at)}`;
  const summary = snap.changes.map((c) => `${changePrefix(c.kind)} ${c.label}`).join(", ");
  if (snap.is_current && !summary) return `Current gear (${when})`;
  return summary ? `${when}: ${summary}` : when;
}

function dotKey(snap: CharacterSnapshotMeta): string {
  return snap.is_current ? "current" : String(snap.id);
}

export type SnapshotChangeTier = "none" | "minimal" | "moderate" | "heavy" | "massive";

/**
 * Gear-change intensity for timeline dots.
 *
 * Buckets (character gear has few items, so counts stay low):
 * - none: 0 changes
 * - minimal: 1–2 changes (< 3; covers "less than 2" plus an adjacent single-slot swap)
 * - moderate: 3–5 changes
 * - heavy: 6–10 changes ("5 to 10" with 5 in moderate)
 * - massive: 11+ changes
 */
export function snapshotChangeTier(changeCount: number): SnapshotChangeTier {
  if (changeCount <= 0) return "none";
  if (changeCount < 3) return "minimal";
  if (changeCount <= 5) return "moderate";
  if (changeCount <= 10) return "heavy";
  return "massive";
}

/** Dot fill/border by gear change count (unselected state). Uses app rarity + ember tokens. */
export function snapshotDotColorClass(changeCount: number): string {
  switch (snapshotChangeTier(changeCount)) {
    case "none":
      return "border-ink-600 bg-ink-600";
    case "minimal":
      return "border-rarity-magic/60 bg-rarity-magic";
    case "moderate":
      return "border-rarity-rare/70 bg-rarity-rare";
    case "heavy":
      return "border-rarity-unique/80 bg-rarity-unique";
    case "massive":
      return "border-ember-400 bg-ember-500";
  }
}

export function CharacterSnapshotTimeline({
  characterName,
  selectedId,
  onSelect,
}: CharacterSnapshotTimelineProps) {
  const snapshotsQ = useCharacterSnapshots(characterName);
  const snapshots = useMemo(
    () => snapshotsQ.data?.snapshots ?? [],
    [snapshotsQ.data?.snapshots],
  );

  const selectedSnap = useMemo(() => {
    if (selectedId === "current") {
      return snapshots.find((s) => s.is_current) ?? null;
    }
    return snapshots.find((s) => s.id === selectedId) ?? null;
  }, [selectedId, snapshots]);

  const changeCount = selectedSnap?.changes.length ?? 0;
  const [changesExpanded, setChangesExpanded] = useState(false);

  return (
    <div
      className="flex flex-col gap-2 rounded-md border border-ink-700/60 bg-ink-900/25 px-2 py-2"
      data-testid="character-snapshot-timeline"
      aria-busy={snapshotsQ.isLoading}
    >
      <p className="text-[10px] uppercase tracking-wide text-parchment-200/55">Gear snapshots</p>
      {snapshotsQ.isLoading && (
        <p className="text-xs text-ui-muted" role="status">
          Loading snapshot timeline&hellip;
        </p>
      )}
      {!snapshotsQ.isLoading && snapshots.length === 0 && (
        <p className="text-xs text-ui-muted" role="status">
          No snapshots yet — refresh after gear changes to build history.
        </p>
      )}
      {snapshots.length > 0 && (
        <div className="relative min-w-0 px-0.5 pt-1">
          <div
            className="pointer-events-none absolute left-3 right-3 top-[0.65rem] h-px bg-ink-700/90"
            aria-hidden
          />
          <ul
            className="relative z-[1] flex min-w-0 gap-1 overflow-x-auto pb-1"
            role="tablist"
            aria-label="Gear snapshot timeline"
          >
            {snapshots.map((snap) => {
              const active = isSelected(snap, selectedId);
              const changeColor = snapshotDotColorClass(snap.changes.length);
              const changeTier = snapshotChangeTier(snap.changes.length);
              return (
                <li
                  key={dotKey(snap)}
                  className="flex min-w-[3.5rem] shrink-0 flex-col items-center gap-0.5"
                >
                  <button
                    type="button"
                    role="tab"
                    aria-selected={active}
                    aria-label={selectionLabel(snap)}
                    title={selectionLabel(snap)}
                    onClick={() => onSelect(snap.is_current ? "current" : (snap.id as number))}
                    className={[
                      "h-3 w-3 shrink-0 rounded-full border transition focus:outline-none focus-visible:ring-2 focus-visible:ring-ember-400/70",
                      active
                        ? "border-ember-300 bg-ember-400 ring-2 ring-ember-400/35"
                        : `${changeColor} hover:border-ink-500`,
                    ].join(" ")}
                    data-testid={snap.is_current ? "snapshot-dot-current" : `snapshot-dot-${snap.id}`}
                    data-change-count={snap.changes.length}
                    data-change-tier={changeTier}
                  />
                  <time
                    className="w-full text-center text-[9px] leading-tight text-parchment-200/80"
                    dateTime={snap.fetched_at}
                  >
                    <span className="block">{formatSnapshotDate(snap.fetched_at)}</span>
                    <span className="block">{formatSnapshotTime(snap.fetched_at)}</span>
                  </time>
                </li>
              );
            })}
          </ul>
        </div>
      )}
      {selectedSnap && changeCount > 0 && (
        <>
          <button
            type="button"
            aria-expanded={changesExpanded}
            aria-controls="snapshot-change-list"
            onClick={() => setChangesExpanded((e) => !e)}
            className="flex w-full items-center justify-between rounded-md border border-ink-700/60 bg-ink-900/30 px-2 py-1 text-left text-xs text-parchment-200/80 transition hover:bg-ink-800/40 focus:outline-none focus-visible:ring-2 focus-visible:ring-ember-400/70"
            data-testid="snapshot-changes-toggle"
          >
            <span>
              {changeCount} change{changeCount === 1 ? "" : "s"}
            </span>
            <span aria-hidden>{changesExpanded ? "▾" : "▸"}</span>
          </button>
          {changesExpanded && (
            <ul
              id="snapshot-change-list"
              className="rounded-md border border-ink-700/80 bg-ink-900/40 px-3 py-2 text-xs text-parchment-100/90"
              data-testid="snapshot-change-list"
            >
              {selectedSnap.changes.map((change, idx) => (
                <li
                  key={`${change.kind}-${change.label}-${idx}`}
                  className={
                    change.kind === "new"
                      ? "text-emerald-300/90"
                      : change.kind === "removed"
                        ? "text-parchment-400 line-through"
                        : "text-amber-200/90"
                  }
                >
                  {changePrefix(change.kind)} {change.label}
                </li>
              ))}
            </ul>
          )}
        </>
      )}
      {selectedSnap?.is_current && selectedSnap.changes.length === 0 && (
        <p className="text-xs text-ui-muted" data-testid="snapshot-current-hint">
          Current gear — select an earlier dot to view past snapshots.
        </p>
      )}
    </div>
  );
}
