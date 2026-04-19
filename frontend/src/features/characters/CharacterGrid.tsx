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
    <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4">
      {characters.map((character) => (
        <button
          key={character.id}
          type="button"
          onClick={() => onSelect(character.name)}
          className={[
            "panel px-3 py-2 text-left transition hover:border-ember-400/80 focus:outline-none",
            selected === character.name ? "ring-2 ring-ember-400" : "",
          ].join(" ")}
        >
          <div className="font-display text-parchment-50">{character.name}</div>
          <div className="text-xs text-ink-500">
            Lv {character.level} {character.class}
          </div>
        </button>
      ))}
    </div>
  );
}
