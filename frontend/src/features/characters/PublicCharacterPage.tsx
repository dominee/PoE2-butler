import { useParams } from "react-router-dom";

import { usePublicCharacter } from "@/api/hooks";
import { ApiError } from "@/api/client";
import { AppFooter } from "@/features/app/AppFooter";
import { CharacterDetailedGearView } from "@/features/characters/CharacterDetailedGearView";
import { CharacterGearDisplay } from "@/features/characters/CharacterGearDisplay";
import { CharacterStatSummary } from "@/features/characters/CharacterStatSummary";
import {
  collectCharacterSkillGemsForDisplay,
  collectCharacterSupportGemsForDisplay,
} from "@/features/characters/characterGemFilter";
import { collectPaperDollItems } from "@/features/characters/paperDollItems";
import { PANE_SECTION_HEADING } from "@/features/items/ItemModPresentation";

export function PublicCharacterPage() {
  const { shareId } = useParams<{ shareId: string }>();
  const q = usePublicCharacter(shareId);

  if (q.isLoading) {
    return (
      <div className="flex min-h-full flex-col">
        <main className="flex flex-1 items-center justify-center p-8 text-ui-muted">
          Loading shared character&hellip;
        </main>
        <AppFooter className="pb-6" />
      </div>
    );
  }

  if (q.isError && q.error) {
    const st = q.error instanceof ApiError ? q.error.status : 0;
    return (
      <div className="flex min-h-full flex-col">
        <main className="flex flex-1 flex-col items-center justify-center gap-3 p-8 text-center">
          <p className="text-parchment-100/90">
            {st === 404
              ? "This share link is invalid, expired, or was revoked."
              : "This shared character could not be loaded."}
          </p>
          <a className="btn-ghost text-sm" href="/">
            Home
          </a>
        </main>
        <AppFooter className="pb-6" />
      </div>
    );
  }

  if (!q.data) return null;

  const { character, league, view_mode: viewMode } = q.data;
  const { summary } = character;
  const skillGems = collectCharacterSkillGemsForDisplay(character);
  const supportGems = collectCharacterSupportGemsForDisplay(character);

  return (
    <div className="flex min-h-full flex-col">
      <header className="shrink-0 border-b border-ink-800 bg-ink-900/60 px-4 py-3 text-sm text-parchment-100/80 backdrop-blur">
        <p className={PANE_SECTION_HEADING}>Public character snapshot</p>
        <h1 className="mt-1 font-display text-lg font-semibold text-amber-100/95">{summary.name}</h1>
        <p className="text-ui-muted">
          Lv {summary.level} · {summary.class} · {league}
        </p>
        {character.is_historical && character.snapshot_fetched_at && (
          <p className="mt-1 text-xs text-amber-200/80">
            Historic snapshot ·{" "}
            {new Date(character.snapshot_fetched_at).toLocaleString(undefined, {
              month: "short",
              day: "numeric",
              hour: "2-digit",
              minute: "2-digit",
            })}
          </p>
        )}
        <p className="mt-2 max-w-2xl text-xs text-ui-muted">
          This page shows a read-only character gear snapshot ({viewMode} view). Anyone with the
          link can see it.{" "}
          <a className="text-ember-400 hover:underline" href="/app">
            Go to Hideout Butler
          </a>
        </p>
      </header>
      <main
        className={`mx-auto w-full flex-1 space-y-4 p-4 ${viewMode === "detailed" ? "max-w-6xl" : "max-w-3xl"}`}
      >
        <CharacterStatSummary detail={character} />
        {viewMode === "simple" ? (
          <CharacterGearDisplay detail={character} readOnly />
        ) : (
          <CharacterDetailedGearView
            equipped={collectPaperDollItems(character)}
            jewels={character.jewels}
            gems={skillGems}
            supportGems={supportGems}
          />
        )}
      </main>
      <AppFooter className="pb-6" />
    </div>
  );
}
