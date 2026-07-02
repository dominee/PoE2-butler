import { useState } from "react";

import type { CharacterSummary } from "@/api/types";
import { CharacterGrid } from "@/features/characters/CharacterGrid";
import { CharacterPaneGothicBackdrop } from "@/features/characters/CharacterPaneGothicBackdrop";
import { PANE_SECTION_HEADING } from "@/features/items/ItemModPresentation";

export interface CharacterListPanelProps {
  characters: CharacterSummary[] | undefined;
  isLoading: boolean;
  selected: string | null;
  onSelect: (name: string) => void;
}

export function CharacterListPanel({
  characters,
  isLoading,
  selected,
  onSelect,
}: CharacterListPanelProps) {
  const [collapsed, setCollapsed] = useState(false);
  const count = characters?.length ?? 0;

  return (
    <section
      aria-label="Characters"
      className={[
        "relative flex min-h-0 flex-col overflow-hidden rounded-sm border border-ink-800/70 bg-ink-950/40 shadow-[inset_0_1px_0_rgba(200,170,120,0.04)] transition-all duration-200",
        collapsed ? "w-9 min-w-[2.25rem]" : "min-w-[13rem] w-full",
      ].join(" ")}
    >
      <CharacterPaneGothicBackdrop />
      <button
        type="button"
        aria-expanded={!collapsed}
        aria-controls="character-list-content"
        onClick={() => setCollapsed((c) => !c)}
        className="relative z-10 flex shrink-0 items-center justify-between px-2 py-2 text-ui-muted transition hover:text-parchment-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-ember-400/70 focus-visible:ring-offset-2 focus-visible:ring-offset-ink-900"
        title={collapsed ? "Expand character list" : "Collapse character list"}
      >
        <span className="text-sm" aria-hidden>
          &#9786;
        </span>
        {collapsed && count > 0 && (
          <span className="ml-0.5 rounded-full bg-ember-500 px-1 text-[9px] font-bold text-ink-950">
            {count > 99 ? "99+" : count}
          </span>
        )}
        {!collapsed && <span className={PANE_SECTION_HEADING}>Characters</span>}
        <span className="ml-auto text-xs">{collapsed ? "›" : "‹"}</span>
      </button>
      {!collapsed && (
        <div
          id="character-list-content"
          className="relative z-10 flex min-h-0 flex-1 flex-col gap-2 overflow-y-auto px-3 pb-3"
        >
          {isLoading && <p className="text-ui-muted">Loading characters&hellip;</p>}
          {characters && (
            <CharacterGrid characters={characters} selected={selected} onSelect={onSelect} />
          )}
        </div>
      )}
    </section>
  );
}
