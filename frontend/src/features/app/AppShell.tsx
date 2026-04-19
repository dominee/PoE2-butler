import { useEffect, useState } from "react";

import {
  useCharacter,
  useCharacters,
  useLeagues,
  useLogout,
  useMe,
  usePrefs,
  useRefresh,
} from "@/api/hooks";
import type { Item } from "@/api/types";
import { CharacterGrid } from "@/features/characters/CharacterGrid";
import { PaperDoll } from "@/features/characters/PaperDoll";
import { ItemDetailPane } from "@/features/items/ItemDetailPane";
import { StashBrowser } from "@/features/stashes/StashBrowser";
import { useUIStore } from "@/store/uiStore";

export function AppShell() {
  const { data: me, isLoading: meLoading, error: meError } = useMe();
  const leaguesQ = useLeagues();
  const prefsQ = usePrefs();
  const refresh = useRefresh();
  const logout = useLogout();

  const selectedLeague = useUIStore((state) => state.selectedLeague);
  const selectedCharacter = useUIStore((state) => state.selectedCharacter);
  const view = useUIStore((state) => state.view);
  const setLeague = useUIStore((state) => state.setLeague);
  const setCharacter = useUIStore((state) => state.setCharacter);
  const setView = useUIStore((state) => state.setView);

  const [selectedItem, setSelectedItem] = useState<Item | null>(null);

  useEffect(() => {
    if (!selectedLeague && leaguesQ.data?.current) {
      setLeague(leaguesQ.data.current);
    }
  }, [leaguesQ.data, selectedLeague, setLeague]);

  const charactersQ = useCharacters(selectedLeague);
  const characterQ = useCharacter(selectedCharacter);

  useEffect(() => {
    setSelectedItem(null);
  }, [selectedCharacter, view]);

  if (meError) {
    return (
      <main className="grid min-h-full place-items-center p-8 text-center">
        <div className="panel max-w-md p-6">
          <p>You are not signed in.</p>
          <a href="/api/auth/login" className="btn-primary mt-4">
            Sign in with GGG
          </a>
        </div>
      </main>
    );
  }

  if (meLoading || !me) {
    return <main className="p-8 text-ink-500">Loading&hellip;</main>;
  }

  return (
    <div className="flex min-h-full flex-col">
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
        <div className="ml-auto flex items-center gap-2">
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
          <button type="button" className="btn-ghost text-sm" onClick={() => logout.mutate()}>
            Logout
          </button>
        </div>
      </header>

      {view === "characters" ? (
        <main className="grid flex-1 gap-4 p-4 lg:grid-cols-[280px,1fr,360px]">
          <section aria-label="Characters" className="space-y-3">
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

          <section aria-label="Equipped gear" className="space-y-3">
            <h2 className="font-display text-parchment-100/80">
              {selectedCharacter ? `${selectedCharacter} — equipped` : "Select a character"}
            </h2>
            {selectedCharacter && characterQ.isLoading && (
              <p className="text-ink-500">Loading gear&hellip;</p>
            )}
            {characterQ.data && (
              <PaperDoll
                equipped={characterQ.data.equipped}
                selectedItemId={selectedItem?.id ?? null}
                onSelectItem={setSelectedItem}
              />
            )}
          </section>

          <ItemDetailPane
            item={selectedItem}
            league={selectedLeague}
            prefs={prefsQ.data}
            onClose={() => setSelectedItem(null)}
          />
        </main>
      ) : (
        <main className="grid flex-1 gap-4 p-4 lg:grid-cols-[1fr,360px]">
          <StashBrowser
            league={selectedLeague}
            selectedItemId={selectedItem?.id ?? null}
            onSelectItem={setSelectedItem}
            valuableThreshold={prefsQ.data?.valuable_threshold_chaos}
          />
          <ItemDetailPane
            item={selectedItem}
            league={selectedLeague}
            prefs={prefsQ.data}
            onClose={() => setSelectedItem(null)}
          />
        </main>
      )}
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
