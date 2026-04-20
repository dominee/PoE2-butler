import type { CharacterSummary } from "@/api/types";

export interface CharacterGridProps {
  characters: CharacterSummary[];
  selected: string | null;
  onSelect: (name: string) => void;
}

export function CharacterGrid({ characters, selected, onSelect }: CharacterGridProps) {
  if (characters.length === 0) {
    return (
      <div className="panel p-4 text-sm text-ink-500">
        No characters found for this league.
      </div>
    );
  }
  return (
    <div className="flex flex-col gap-1.5">
      {characters.map((character) => (
        <button
          key={character.id}
          type="button"
          onClick={() => onSelect(character.name)}
          className={[
            "panel flex w-full items-center justify-between px-3 py-2.5 text-left",
            "transition hover:border-ember-400/80 focus:outline-none",
            selected === character.name ? "ring-2 ring-ember-400" : "",
          ].join(" ")}
        >
          <div className="min-w-0">
            <div className="truncate font-display text-parchment-50">{character.name}</div>
            <div className="text-xs text-ink-500">
              Lv {character.level} &middot; {character.class}
            </div>
          </div>
          {selected === character.name && (
            <span className="ml-2 shrink-0 text-xs text-ember-400">&#9654;</span>
          )}
        </button>
      ))}
    </div>
  );
}
