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
import type { Item } from "@/api/types";
import { ActivityLog } from "@/features/activity/ActivityLog";
import { CurrencyExchangeHint } from "@/features/app/CurrencyExchangeHint";
import { AppFooter } from "@/features/app/AppFooter";
import { HeaderCurrencyRates } from "@/features/app/HeaderCurrencyRates";
import { CharacterGrid } from "@/features/characters/CharacterGrid";
import { CharacterStatSummary } from "@/features/characters/CharacterStatSummary";
import { CharacterTable } from "@/features/characters/CharacterTable";
import { PaperDoll } from "@/features/characters/PaperDoll";
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

  useEffect(() => {
    if (!selectedLeague && leaguesQ.data?.current) {
      setLeague(leaguesQ.data.current);
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
  const characterQ = useCharacter(characterNameForDetail);

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
        <main className="flex-1 p-8 text-ink-500">Loading&hellip;</main>
        <AppFooter className="pb-6" />
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col">
      <header className="flex flex-wrap items-center gap-3 border-b border-ink-800 bg-ink-900/60 px-4 py-2 backdrop-blur">
        <h1 className="font-display text-lg text-ember-400">PoE2 Butler</h1>
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
            className="btn-ghost text-sm"
            onClick={() => refresh.mutate()}
            disabled={refresh.isPending}
          >
            {refresh.isPending ? "Refreshing\u2026" : "Refresh"}
          </button>
          <button
            type="button"
            className="btn-ghost text-sm"
            title="Queue hybrid price checks for stash items (no estimate first; capped)"
            aria-label="Apprise: queue stash price checks"
            onClick={() => {
              if (!selectedLeague) return;
              apprise.mutate({ league: selectedLeague });
            }}
            disabled={!selectedLeague || apprise.isPending}
          >
            {apprise.isPending ? "Apprising\u2026" : "Apprise"}
          </button>
          <button type="button" className="btn-ghost text-sm" onClick={() => logout.mutate()}>
            Logout
          </button>
        </div>
      </header>

      {view === "characters" ? (
        <main className="flex min-h-0 flex-1 overflow-hidden">
        <ActivityLog league={selectedLeague} onSelectItem={setSelectedItem} />
        <div className="grid min-h-0 flex-1 gap-4 overflow-hidden p-4 lg:grid-cols-[280px,1fr,360px]">
          <section aria-label="Characters" className="flex flex-col gap-2 overflow-y-auto">
            <h2 className="font-display text-parchment-100/80">Characters</h2>
            {charactersQ.isLoading && <p className="text-ink-500">Loading characters&hellip;</p>}
            {charactersQ.data && (
              <CharacterGrid
                characters={charactersQ.data.characters}
                selected={selectedCharacter}
                onSelect={setCharacter}
              />
            )}
          </section>

          <section aria-label="Equipped gear" className="flex flex-col gap-2 overflow-y-auto">
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div className="min-w-0 flex-1">
                <h2 className="font-display text-parchment-100/80">
                  {selectedCharacter ? `${selectedCharacter} — equipped` : "Select a character"}
                </h2>
                <CurrencyExchangeHint league={selectedLeague} className="mt-0.5" />
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
              <p className="text-ink-500" aria-live="polite">
                {gearLoadStatus}
              </p>
            )}
            {selectedCharacter && characterQ.isError && (
              <p className="text-ink-500" role="alert">
                Stage 3/3: Gear request failed — check Network for GET /api/characters/
                {encodeURIComponent(selectedCharacter)}. Try another character or Refresh.
              </p>
            )}
            {characterQ.data && charLayout === "doll" && (
              <>
                <PaperDoll
                  equipped={characterQ.data.equipped}
                  selectedItemId={selectedItem?.id ?? null}
                  onSelectItem={setSelectedItem}
                />
                {characterQ.data.inventory.length > 0 && (
                  <div className="mt-2">
                    <h3 className="mb-1 text-xs font-semibold uppercase tracking-widest text-ink-500">
                      Jewels
                    </h3>
                    <div className="grid grid-cols-2 gap-1.5">
                      {characterQ.data.inventory.map((jewel) => (
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
              </>
            )}
            {characterQ.data && charLayout === "table" && (
              <CharacterTable
                equipped={characterQ.data.equipped}
                jewels={characterQ.data.inventory}
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
  );
}

function viewBtn(active: boolean): string {
  return [
    "rounded-md border px-2 py-1 transition",
    active
      ? "border-ember-400 bg-ember-500/10 text-ember-200"
      : "border-ink-700 bg-ink-800 text-parchment-100 hover:border-ember-400",
  ].join(" ");
}

function charLayoutBtn(active: boolean): string {
  return [
    "px-3 py-1 transition",
    active ? "bg-ember-500/10 text-ember-200" : "text-parchment-100",
  ].join(" ");
}
