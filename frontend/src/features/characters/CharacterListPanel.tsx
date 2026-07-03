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
      <div
        className={[
          "relative z-10 flex shrink-0 px-2 py-2",
          collapsed ? "flex-col items-center gap-1" : "items-center gap-1.5",
        ].join(" ")}
      >
        <button
          type="button"
          aria-expanded={!collapsed}
          aria-controls="character-list-content"
          onClick={() => setCollapsed((c) => !c)}
          className={[
            "text-ui-muted transition hover:text-parchment-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-ember-400/70 focus-visible:ring-offset-2 focus-visible:ring-offset-ink-900",
            collapsed
              ? "flex flex-col items-center gap-0.5"
              : "flex min-w-0 flex-1 items-center gap-1.5",
          ].join(" ")}
          title={collapsed ? "Expand character list" : "Collapse character list"}
        >
          <span aria-hidden className="text-sm font-semibold leading-none">
            {collapsed ? "+" : "−"}
          </span>
          {!collapsed && <span className={PANE_SECTION_HEADING}>Characters</span>}
          {!collapsed && <span className="ml-auto text-xs">‹</span>}
        </button>
        {collapsed && count > 0 && (
          <span
            className="rounded-full bg-ember-500 px-1 text-[9px] font-bold leading-tight text-ink-950"
            title={`${count} character${count === 1 ? "" : "s"}`}
          >
            {count > 99 ? "99+" : count}
          </span>
        )}
      </div>
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
