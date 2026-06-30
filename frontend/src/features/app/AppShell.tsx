import { useEffect, useMemo, useState } from "react";

import {
  useApprise,
  useCharacter,
  useCharacters,
  useLeagues,
  useLogout,
  useMe,
  usePrefs,
  useRefresh,
} from "@/api/hooks";
import { ApiError } from "@/api/client";
import type { Item } from "@/api/types";
import { ActivityLog } from "@/features/activity/ActivityLog";
import { AppFooter } from "@/features/app/AppFooter";
import { HeaderCurrencyRates } from "@/features/app/HeaderCurrencyRates";
import { CharacterGrid } from "@/features/characters/CharacterGrid";
import { CharacterPaneGothicBackdrop } from "@/features/characters/CharacterPaneGothicBackdrop";
import { CharacterStatSummary } from "@/features/characters/CharacterStatSummary";
import { PANE_SECTION_HEADING } from "@/features/items/ItemModPresentation";
import { CharacterTable } from "@/features/characters/CharacterTable";
import { filterNotableCharacterGems, isNotableCharacterGem } from "@/features/characters/characterGemFilter";
import { PaperDoll } from "@/features/characters/PaperDoll";
import { collectPaperDollItems } from "@/features/characters/paperDollItems";
import { PriceInflightProvider } from "@/features/pricing/PriceInflightContext";
import { ItemCard } from "@/features/items/ItemCard";
import { ItemDetailPane } from "@/features/items/ItemDetailPane";
import { StashBrowser } from "@/features/stashes/StashBrowser";
import { useUIStore } from "@/store/uiStore";

export function AppShell() {
  const { data: me, isLoading: meLoading, error: meError } = useMe();
  const leaguesQ = useLeagues();
  const prefsQ = usePrefs();
  const refresh = useRefresh();
  const apprise = useApprise();
  const logout = useLogout();

  const selectedLeague = useUIStore((state) => state.selectedLeague);
  const selectedCharacter = useUIStore((state) => state.selectedCharacter);
  const view = useUIStore((state) => state.view);
  const setLeague = useUIStore((state) => state.setLeague);
  const setCharacter = useUIStore((state) => state.setCharacter);
  const setView = useUIStore((state) => state.setView);

  const [selectedItem, setSelectedItem] = useState<Item | null>(null);
  const [charLayout, setCharLayout] = useState<"doll" | "table">("doll");
  const [appriseNotice, setAppriseNotice] = useState<string | null>(null);

  useEffect(() => {
    if (!selectedLeague) {
      const autoSelect = leaguesQ.data?.current ?? leaguesQ.data?.preferred;
      if (autoSelect) setLeague(autoSelect);
    }
  }, [leaguesQ.data, selectedLeague, setLeague]);

  const charactersQ = useCharacters(selectedLeague);
  // Persisted `selectedCharacter` can belong to another account until the roster loads; avoid
  // hammering `/api/characters/:name` (long mock scrape + backend ReadTimeout) for a stale name.
  const characterNameForDetail = useMemo(() => {
    if (!selectedCharacter) return null;
    if (!charactersQ.data || charactersQ.isError) return null;
    return charactersQ.data.characters.some((c) => c.name === selectedCharacter)
      ? selectedCharacter
      : null;
  }, [selectedCharacter, charactersQ.data, charactersQ.isError]);
  const characterQ = useCharacter(characterNameForDetail, selectedLeague);

  const gearLoadStatus = useMemo(() => {
    if (!selectedCharacter) return null;
    if (charactersQ.isError) {
      return "Stage 0/3: Character list failed — open DevTools → Network for GET /api/characters?league=…";
    }
    if (!characterNameForDetail) {
      if (charactersQ.isLoading || charactersQ.isFetching) {
        return "Stage 1/3: Loading roster for this league…";
      }
      if (charactersQ.data?.characters.length === 0) {
        return "Stage 1/3: No characters in this league — pick another league or Refresh.";
      }
      if (charactersQ.data) {
        return "Stage 1/3: Selected name is not in this league roster (selection will clear)…";
      }
      return "Stage 1/3: Waiting for character list…";
    }
    if (characterQ.isError) return null;
    if (characterQ.fetchStatus === "fetching" && characterQ.data === undefined) {
      return `Stage 2/3: Fetching gear — GET /api/characters/${encodeURIComponent(characterNameForDetail)}`;
    }
    if (characterQ.data === undefined && characterQ.status === "pending") {
      return `Stage 2/3: Queued — preparing request for ${characterNameForDetail}…`;
    }
    return null;
  }, [
    selectedCharacter,
    characterNameForDetail,
    charactersQ.isError,
    charactersQ.isLoading,
    charactersQ.isFetching,
    charactersQ.data,
    characterQ.isError,
    characterQ.fetchStatus,
    characterQ.status,
    characterQ.data,
  ]);

  useEffect(() => {
    if (!import.meta.env.DEV || !selectedCharacter) return;
    console.log("[PoE2Butler][gear]", {
      selectedCharacter,
      characterNameForDetail,
      rosterStatus: charactersQ.status,
      rosterFetch: charactersQ.fetchStatus,
      detailStatus: characterQ.status,
      detailFetch: characterQ.fetchStatus,
      gearLoadStatus,
    });
  }, [
    selectedCharacter,
    characterNameForDetail,
    charactersQ.status,
    charactersQ.fetchStatus,
    characterQ.status,
    characterQ.fetchStatus,
    gearLoadStatus,
  ]);

  // Persisted UI can keep a character name from a previous session; that fires a useless
  // detail request (404 or long mock timeout) and blocks the gear panel until it settles.
  useEffect(() => {
    if (charactersQ.isLoading || charactersQ.isError || !charactersQ.data) return;
    if (!selectedCharacter) return;
    const roster = charactersQ.data.characters;
    const inRoster = roster.some((c) => c.name === selectedCharacter);
    if (!inRoster) setCharacter(null);
  }, [
    charactersQ.isLoading,
    charactersQ.isError,
    charactersQ.data,
    selectedCharacter,
    setCharacter,
  ]);

  useEffect(() => {
    setSelectedItem(null);
  }, [selectedCharacter, view]);

  if (meError) {
    return (
      <div className="flex min-h-full flex-col">
        <main className="grid flex-1 place-items-center p-8 text-center">
          <div className="panel max-w-md p-6">
            <p>You are not signed in.</p>
            <a href="/api/auth/login" className="btn-primary mt-4">
              Sign in with GGG
            </a>
          </div>
        </main>
        <AppFooter className="pb-6" />
      </div>
    );
  }

  if (meLoading || !me) {
    return (
      <div className="flex min-h-full flex-col">
        <main className="flex-1 p-8 text-ui-muted">Loading&hellip;</main>
        <AppFooter className="pb-6" />
      </div>
    );
  }

  return (
    <PriceInflightProvider league={selectedLeague}>
    <div className="flex h-full flex-col">
      <header className="flex flex-wrap items-center gap-3 border-b border-ink-950 bg-ink-950/70 px-4 py-2 backdrop-blur">
        <h1 className="font-display text-lg text-ember-400">Hideout Butler</h1>
        <span className="text-sm text-parchment-100/80">{me.account_name}</span>
        <nav aria-label="Primary view" className="ml-3 flex gap-1 text-sm">
          <button
            type="button"
            className={viewBtn(view === "characters")}
            onClick={() => setView("characters")}
            aria-current={view === "characters" ? "page" : undefined}
          >
            Characters
          </button>
          <button
            type="button"
            className={viewBtn(view === "stashes")}
            onClick={() => setView("stashes")}
            aria-current={view === "stashes" ? "page" : undefined}
          >
            Stash
          </button>
        </nav>
        <div className="ml-auto flex flex-wrap items-center gap-2 sm:gap-3">
          <HeaderCurrencyRates league={selectedLeague} />
          <select
            value={selectedLeague ?? ""}
            onChange={(event) => setLeague(event.target.value || null)}
            className="rounded-md border border-ink-600 bg-ink-800 px-2 py-1 text-sm"
            aria-label="League"
          >
            {!selectedLeague && <option value="">Select league</option>}
            {leaguesQ.data?.leagues.map((league) => (
              <option key={league.id} value={league.id}>
                {league.id}
              </option>
            ))}
          </select>
          <button
            type="button"
            className="btn-ghost inline-flex items-center gap-1.5 text-sm"
            onClick={() => refresh.mutate({ league: selectedLeague })}
            disabled={refresh.isPending}
          >
            <HeaderSyncIcon className="h-4 w-4 shrink-0 opacity-90" />
            {refresh.isPending ? "Refreshing\u2026" : "Refresh"}
          </button>
          <button
            type="button"
            className="btn-ghost inline-flex items-center gap-1.5 text-sm"
            title="Queue hybrid price checks for stash and character gear (missing estimates first; capped)"
            aria-label="Apprise: queue price checks"
            onClick={() => {
              if (!selectedLeague) return;
              setAppriseNotice(null);
              apprise.mutate(
                { league: selectedLeague },
                {
                  onSuccess: (data) => {
                    setAppriseNotice(`Queued price checks for ${data.league}`);
                    window.setTimeout(() => setAppriseNotice(null), 5000);
                  },
                  onError: (err) => {
                    const detail =
                      err instanceof ApiError &&
                      err.body &&
                      typeof err.body === "object" &&
                      "detail" in err.body
                        ? String((err.body as { detail: unknown }).detail)
                        : err.message;
                    setAppriseNotice(`Apprise failed: ${detail}`);
                  },
                },
              );
            }}
            disabled={!selectedLeague || apprise.isPending}
          >
            <HeaderAppriseIcon className="h-4 w-4 shrink-0 opacity-90" />
            {apprise.isPending ? "Apprising\u2026" : "Apprise"}
          </button>
          {appriseNotice && (
            <span
              className="max-w-[14rem] truncate text-[11px] text-parchment-200/85"
              role="status"
              aria-live="polite"
            >
              {appriseNotice}
            </span>
          )}
          <button type="button" className="btn-ghost text-sm" onClick={() => logout.mutate()}>
            Logout
          </button>
        </div>
      </header>

      {view === "characters" ? (
        <main className="flex min-h-0 flex-1 overflow-hidden">
        <ActivityLog league={selectedLeague} onSelectItem={setSelectedItem} />
        <div className="grid min-h-0 flex-1 gap-4 overflow-hidden p-4 lg:grid-cols-[280px,1fr,360px]">
          <section
            aria-label="Characters"
            className="relative flex min-h-0 flex-col gap-2 overflow-y-auto rounded-sm border border-ink-800/70 bg-ink-950/40 p-3 shadow-[inset_0_1px_0_rgba(200,170,120,0.04)]"
          >
            <CharacterPaneGothicBackdrop />
            <h2 className="relative z-10 shrink-0 font-display text-parchment-100/85 tracking-wide">
              Characters
            </h2>
            {charactersQ.isLoading && (
              <p className="relative z-10 text-ui-muted">Loading characters&hellip;</p>
            )}
            {charactersQ.data && (
              <div className="relative z-10 min-h-0 flex-1">
                <CharacterGrid
                  characters={charactersQ.data.characters}
                  selected={selectedCharacter}
                  onSelect={setCharacter}
                />
              </div>
            )}
          </section>

          <section aria-label="Equipped gear" className="flex flex-col gap-2 overflow-y-auto">
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div className="min-w-0 flex-1">
                <h2 className="font-display text-parchment-100/80">
                  {selectedCharacter ? (
                    <>
                      <span className="font-semibold tracking-wide text-amber-100/95 [text-shadow:0_0_14px_rgba(251,191,36,0.22)]">
                        {selectedCharacter}
                      </span>
                      <span className="font-normal text-parchment-200/70"> — equipped</span>
                    </>
                  ) : (
                    "Select a character"
                  )}
                </h2>
              </div>
              {characterQ.data && (
                <div
                  className="inline-flex shrink-0 rounded-md border border-ink-700 bg-ink-800 text-xs"
                  role="radiogroup"
                  aria-label="Gear layout"
                >
                  <button
                    type="button"
                    role="radio"
                    aria-checked={charLayout === "doll"}
                    onClick={() => setCharLayout("doll")}
                    className={charLayoutBtn(charLayout === "doll")}
                  >
                    Doll
                  </button>
                  <button
                    type="button"
                    role="radio"
                    aria-checked={charLayout === "table"}
                    onClick={() => setCharLayout("table")}
                    className={charLayoutBtn(charLayout === "table")}
                  >
                    Table
                  </button>
                </div>
              )}
            </div>
            {characterQ.data && <CharacterStatSummary detail={characterQ.data} />}
            {gearLoadStatus && (
              <p className="text-ui-muted" aria-live="polite">
                {gearLoadStatus}
              </p>
            )}
            {selectedCharacter && characterQ.isError && (
              <p className="text-amber-200/90" role="alert">
                Stage 3/3: Gear request failed — check Network for GET /api/characters/
                {encodeURIComponent(selectedCharacter)}. Try another character or Refresh.
              </p>
            )}
            {characterNameForDetail &&
              (characterQ.isLoading || (characterQ.isFetching && !characterQ.data)) && (
                <p className="text-ui-muted" aria-live="polite">
                  Loading gear&hellip;
                </p>
              )}
            {characterQ.data && charLayout === "doll" && (
              <>
                <PaperDoll
                  equipped={collectPaperDollItems(characterQ.data)}
                  selectedItemId={selectedItem?.id ?? null}
                  onSelectItem={setSelectedItem}
                />
                {characterQ.data.jewels?.length > 0 && (
                  <div className="mt-2">
                    <h3 className={`mb-1 ${PANE_SECTION_HEADING}`}>Jewels</h3>
                    <div className="grid grid-cols-2 gap-1.5">
                      {characterQ.data.jewels.map((jewel) => (
                        <ItemCard
                          key={jewel.id}
                          item={jewel}
                          selected={selectedItem?.id === jewel.id}
                          onClick={setSelectedItem}
                        />
                      ))}
                    </div>
                  </div>
                )}
                {filterNotableCharacterGems(characterQ.data.gems ?? []).length > 0 && (
                  <div className="mt-2">
                    <h3 className={`mb-1 ${PANE_SECTION_HEADING}`}>Skill gems</h3>
                    <div className="grid grid-cols-2 gap-1.5">
                      {filterNotableCharacterGems(characterQ.data.gems ?? []).map((gem) => (
                        <ItemCard
                          key={gem.id}
                          item={gem}
                          selected={selectedItem?.id === gem.id}
                          onClick={setSelectedItem}
                        />
                      ))}
                    </div>
                  </div>
                )}
                {(characterQ.data.inventory ?? []).filter(
                  (i) => i.rarity !== "Gem" || isNotableCharacterGem(i),
                ).length > 0 && (
                  <div className="mt-2">
                    <h3 className={`mb-1 ${PANE_SECTION_HEADING}`}>Other</h3>
                    <div className="grid grid-cols-2 gap-1.5">
                      {(characterQ.data.inventory ?? [])
                        .filter((i) => i.rarity !== "Gem" || isNotableCharacterGem(i))
                        .map((item) => (
                        <ItemCard
                          key={item.id}
                          item={item}
                          selected={selectedItem?.id === item.id}
                          onClick={setSelectedItem}
                        />
                      ))}
                    </div>
                  </div>
                )}
              </>
            )}
            {characterQ.data && charLayout === "table" && (
              <CharacterTable
                equipped={characterQ.data.equipped}
                gems={characterQ.data.gems}
                jewels={characterQ.data.jewels}
                other={characterQ.data.inventory}
                selectedItemId={selectedItem?.id ?? null}
                onSelect={setSelectedItem}
              />
            )}
          </section>

          <ItemDetailPane
            item={selectedItem}
            league={selectedLeague}
            prefs={prefsQ.data}
            onClose={() => setSelectedItem(null)}
          />
        </div>
        </main>
      ) : (
        <main className="flex min-h-0 flex-1 overflow-hidden">
        <ActivityLog league={selectedLeague} onSelectItem={setSelectedItem} />
        <div className="grid min-h-0 flex-1 gap-4 overflow-hidden p-4 lg:grid-cols-[1fr,360px]">
          <div className="overflow-y-auto">
            <StashBrowser
              league={selectedLeague}
              selectedItemId={selectedItem?.id ?? null}
              onSelectItem={setSelectedItem}
              valuableThreshold={prefsQ.data?.valuable_threshold_chaos}
            />
          </div>
          <ItemDetailPane
            item={selectedItem}
            league={selectedLeague}
            prefs={prefsQ.data}
            onClose={() => setSelectedItem(null)}
          />
        </div>
        </main>
      )}
      <AppFooter className="border-t border-ink-800 bg-ink-900/60 py-2" />
    </div>
    </PriceInflightProvider>
  );
}

function viewBtn(active: boolean): string {
  return [
    "rounded-md border px-2 py-1 transition focus:outline-none focus-visible:ring-2 focus-visible:ring-ember-400/70",
    active
      ? "border-ember-400 bg-ember-500/10 text-ember-200"
      : "border-ink-700 bg-ink-800 text-parchment-100 hover:border-ember-400",
  ].join(" ");
}

function charLayoutBtn(active: boolean): string {
  return [
    "px-3 py-1 transition focus:outline-none focus-visible:ring-2 focus-visible:ring-ember-400/60 focus-visible:ring-inset",
    active ? "bg-ember-500/10 text-ember-200" : "text-parchment-100",
  ].join(" ");
}

/** Same glyph as detail-pane “Refresh pricing” — inventory sync from GGG / mock. */
function HeaderSyncIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
    >
      <path d="M23 4v6h-6" />
      <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10" />
    </svg>
  );
}

/** Bars — queue stash price estimates. */
function HeaderAppriseIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
    >
      <path d="M7 20V10M12 20V4M17 20v-6" />
    </svg>
  );
}
