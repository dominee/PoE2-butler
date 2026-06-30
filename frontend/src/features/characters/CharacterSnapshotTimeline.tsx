import { useMemo } from "react";

import { useCharacterSnapshots } from "@/api/hooks";
import type { CharacterSnapshotMeta } from "@/api/types";

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

function dotKey(snap: CharacterSnapshotMeta, index: number): string {
  return snap.is_current ? "current" : String(snap.id ?? index);
}

function isSelected(snap: CharacterSnapshotMeta, selectedId: SnapshotSelection): boolean {
  if (snap.is_current) return selectedId === "current";
  return selectedId === snap.id;
}

export function CharacterSnapshotTimeline({
  characterName,
  selectedId,
  onSelect,
}: CharacterSnapshotTimelineProps) {
  const snapshotsQ = useCharacterSnapshots(characterName);
  const snapshots = snapshotsQ.data?.snapshots ?? [];

  const showTimeline = useMemo(
    () => snapshotsQ.isSuccess && snapshots.length > 0,
    [snapshotsQ.isSuccess, snapshots.length],
  );

  if (!showTimeline) return null;

  return (
    <div
      className="relative flex min-w-0 items-center gap-0 px-1 py-2"
      data-testid="character-snapshot-timeline"
    >
      <div
        className="pointer-events-none absolute left-3 right-3 top-1/2 h-px -translate-y-1/2 bg-ink-700/90"
        aria-hidden
      />
      <ul
        className="relative z-[1] flex min-w-0 flex-1 items-center justify-between gap-1"
        role="tablist"
        aria-label="Gear snapshot timeline"
      >
        {snapshots.map((snap, index) => {
          const active = isSelected(snap, selectedId);
          const label = snap.is_current
            ? `Current gear (${formatSnapshotTime(snap.fetched_at)})`
            : `Gear from ${formatSnapshotTime(snap.fetched_at)}`;
          return (
            <li key={dotKey(snap, index)} className="flex shrink-0">
              <button
                type="button"
                role="tab"
                aria-selected={active}
                title={label}
                aria-label={label}
                onClick={() => onSelect(snap.is_current ? "current" : (snap.id as number))}
                className={[
                  "h-3 w-3 rounded-full border transition focus:outline-none focus-visible:ring-2 focus-visible:ring-ember-400/70",
                  active
                    ? "border-ember-300 bg-ember-400 ring-2 ring-ember-400/35"
                    : "border-ink-600 bg-ink-600 hover:border-ink-500 hover:bg-ink-500",
                ].join(" ")}
                data-testid={snap.is_current ? "snapshot-dot-current" : `snapshot-dot-${snap.id}`}
              />
            </li>
          );
        })}
      </ul>
    </div>
  );
}
