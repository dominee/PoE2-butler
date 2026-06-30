import { useMemo } from "react";

import { useCharacterSnapshots } from "@/api/hooks";
import type { CharacterSnapshotChange, CharacterSnapshotMeta } from "@/api/types";

export type SnapshotSelection = number | "current";

export interface CharacterSnapshotTimelineProps {
  characterName: string;
  selectedId: SnapshotSelection;
  onSelect: (id: SnapshotSelection) => void;
}

function formatSnapshotTime(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
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
  const when = formatSnapshotTime(snap.fetched_at);
  const summary = snap.changes.map((c) => `${changePrefix(c.kind)} ${c.label}`).join(", ");
  if (snap.is_current && !summary) return `Current gear (${when})`;
  return summary ? `${when}: ${summary}` : when;
}

function dotKey(snap: CharacterSnapshotMeta): string {
  return snap.is_current ? "current" : String(snap.id);
}

export function CharacterSnapshotTimeline({
  characterName,
  selectedId,
  onSelect,
}: CharacterSnapshotTimelineProps) {
  const snapshotsQ = useCharacterSnapshots(characterName);
  const snapshots = snapshotsQ.data?.snapshots ?? [];

  const selectedSnap = useMemo(() => {
    if (selectedId === "current") {
      return snapshots.find((s) => s.is_current) ?? null;
    }
    return snapshots.find((s) => s.id === selectedId) ?? null;
  }, [selectedId, snapshots]);

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
        <div className="relative min-w-0 px-1 pt-1">
          <div
            className="pointer-events-none absolute left-4 right-4 top-[0.65rem] h-px bg-ink-700/90"
            aria-hidden
          />
          <ul
            className="relative z-[1] flex min-w-0 gap-3 overflow-x-auto pb-1"
            role="tablist"
            aria-label="Gear snapshot timeline"
          >
            {snapshots.map((snap) => {
              const active = isSelected(snap, selectedId);
              return (
                <li
                  key={dotKey(snap)}
                  className="flex min-w-[7.5rem] max-w-[10rem] shrink-0 flex-col items-center gap-1"
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
                        : "border-ink-600 bg-ink-600 hover:border-ink-500 hover:bg-ink-500",
                    ].join(" ")}
                    data-testid={snap.is_current ? "snapshot-dot-current" : `snapshot-dot-${snap.id}`}
                  />
                  <time
                    className="w-full text-center text-[10px] leading-tight text-parchment-200/80"
                    dateTime={snap.fetched_at}
                  >
                    {formatSnapshotTime(snap.fetched_at)}
                  </time>
                </li>
              );
            })}
          </ul>
        </div>
      )}
      {selectedSnap && selectedSnap.changes.length > 0 && (
        <ul
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
      {selectedSnap?.is_current && selectedSnap.changes.length === 0 && (
        <p className="text-xs text-ui-muted" data-testid="snapshot-current-hint">
          Current gear — select an earlier dot to view past snapshots.
        </p>
      )}
    </div>
  );
}
