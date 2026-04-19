import type { StashTabSummary } from "@/api/types";

export interface TabStripProps {
  tabs: StashTabSummary[];
  selected: string | null;
  onSelect: (tabId: string) => void;
}

function colourStyle(tab: StashTabSummary): React.CSSProperties | undefined {
  if (!tab.colour) return undefined;
  const { r, g, b } = tab.colour;
  return {
    borderColor: `rgb(${r}, ${g}, ${b})`,
    boxShadow: `inset 0 -2px 0 rgb(${r}, ${g}, ${b})`,
  };
}

export function TabStrip({ tabs, selected, onSelect }: TabStripProps) {
  if (tabs.length === 0) {
    return (
      <p className="text-ink-500" role="status">
        No stash tabs yet — try Refresh.
      </p>
    );
  }
  return (
    <ul
      className="flex min-w-0 flex-wrap gap-2 overflow-x-auto"
      role="tablist"
      aria-label="Stash tabs"
    >
      {tabs.map((tab) => {
        const isSelected = tab.id === selected;
        return (
          <li key={tab.id}>
            <button
              type="button"
              role="tab"
              aria-selected={isSelected}
              onClick={() => onSelect(tab.id)}
              className={[
                "rounded-md border px-3 py-1 text-sm",
                "transition hover:border-ember-400 focus:outline-none focus-visible:ring-2 focus-visible:ring-ember-400",
                isSelected
                  ? "border-ember-400 bg-ember-500/10 text-ember-200"
                  : "border-ink-700 bg-ink-800 text-parchment-100",
              ].join(" ")}
              style={isSelected ? undefined : colourStyle(tab)}
              data-testid="stash-tab"
            >
              <span>{tab.name}</span>
              <span className="ml-2 text-[10px] uppercase text-ink-500">{tab.type}</span>
            </button>
          </li>
        );
      })}
    </ul>
  );
}
