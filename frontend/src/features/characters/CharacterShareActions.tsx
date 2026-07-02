import { useState } from "react";

import {
  characterShareViewPath,
  useCreateCharacterShare,
  useRevokeCharacterShare,
} from "@/api/hooks";
import type { CharacterDetail } from "@/api/types";
import type { SnapshotSelection } from "@/features/characters/CharacterSnapshotTimeline";
import type { GearEstimate } from "@/features/characters/characterGearItems";
import { CharacterImageExportActions } from "@/features/characters/CharacterImageExport";
import { copyTextToClipboard } from "@/utils/clipboard";
import { IconLinkShare } from "@/features/items/itemPaneIcons";

export interface CharacterShareActionsProps {
  league: string | null;
  characterName: string | null;
  selectedSnapshotId: SnapshotSelection;
  gearDetail: CharacterDetail | undefined;
  gearEstimate?: GearEstimate;
  disabled?: boolean;
}

export function CharacterShareActions({
  league,
  characterName,
  selectedSnapshotId,
  gearDetail,
  gearEstimate,
  disabled = false,
}: CharacterShareActionsProps) {
  const createShare = useCreateCharacterShare();
  const revokeShare = useRevokeCharacterShare();
  const [expanded, setExpanded] = useState(false);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [lastShareId, setLastShareId] = useState<string | null>(null);

  const historyId = selectedSnapshotId === "current" ? null : selectedSnapshotId;
  const canShare = Boolean(league && characterName && gearDetail && !disabled);

  const onCreateShare = async (viewMode: "simple" | "detailed") => {
    if (!league || !characterName) {
      setFeedback("Select a league first.");
      setTimeout(() => setFeedback(null), 4000);
      return;
    }
    try {
      const { share_id: sid } = await createShare.mutateAsync({
        league,
        character_name: characterName,
        history_id: historyId,
        view_mode: viewMode,
      });
      setLastShareId(sid);
      const href = `${window.location.origin}${characterShareViewPath(sid)}`;
      await copyTextToClipboard(href);
      setFeedback(`${viewMode === "simple" ? "Simple" : "Detailed"} link copied`);
    } catch {
      setFeedback("Could not create share.");
    }
    setTimeout(() => setFeedback(null), 4000);
  };

  const onRevokeShare = async () => {
    if (!lastShareId) return;
    try {
      await revokeShare.mutateAsync({ shareId: lastShareId });
      setLastShareId(null);
      setFeedback("Link revoked");
    } catch {
      setFeedback("Could not revoke link");
    }
    setTimeout(() => setFeedback(null), 4000);
  };

  return (
    <div className="relative z-10 shrink-0">
      <button
        type="button"
        className="btn-ghost px-1.5 py-0.5 text-xs"
        aria-expanded={expanded}
        disabled={!canShare}
        onClick={() => setExpanded((e) => !e)}
        title="Share or export character"
      >
        <IconLinkShare />
        <span className="sr-only">Share</span>
      </button>
      {expanded && canShare && gearDetail && league && (
        <div className="absolute left-0 top-full z-20 mt-1 w-56 rounded-md border border-ink-700 bg-ink-900 p-2 shadow-lg">
          <p className="mb-2 text-[10px] text-amber-200/90">
            Anyone with the link can view this gear snapshot.
          </p>
          <div className="flex flex-col gap-1">
            <button
              type="button"
              className="btn-ghost justify-start px-2 py-1 text-xs"
              disabled={createShare.isPending}
              onClick={() => void onCreateShare("simple")}
            >
              Copy simple link
            </button>
            <button
              type="button"
              className="btn-ghost justify-start px-2 py-1 text-xs"
              disabled={createShare.isPending}
              onClick={() => void onCreateShare("detailed")}
            >
              Copy detailed link
            </button>
            {lastShareId && (
              <button
                type="button"
                className="btn-ghost justify-start px-2 py-1 text-xs text-red-300/90"
                disabled={revokeShare.isPending}
                onClick={() => void onRevokeShare()}
              >
                Revoke last link
              </button>
            )}
          </div>
          <hr className="my-2 border-ink-700" />
          <CharacterImageExportActions
            detail={gearDetail}
            league={league}
            gearEstimate={gearEstimate}
          />
          {feedback && <p className="mt-1 text-[10px] text-ember-400">{feedback}</p>}
        </div>
      )}
    </div>
  );
}
