import { useState } from "react";

import { usePriceLookup, useTradeSearch, useUpdatePrefs } from "@/api/hooks";
import type { Item, Prefs } from "@/api/types";

import { PriceBadge } from "./PriceBadge";

export interface ItemDetailPaneProps {
  item: Item | null;
  league: string | null;
  prefs: Prefs | undefined;
  onClose?: () => void;
}

function ModSection({ title, mods, tone }: { title: string; mods: string[]; tone: string }) {
  if (mods.length === 0) return null;
  return (
    <div>
      <h4 className="text-xs uppercase tracking-wide text-ink-500">{title}</h4>
      <ul className={`mt-1 space-y-0.5 text-sm ${tone}`}>
        {mods.map((mod, idx) => (
          <li key={`${title}-${idx}`}>{mod}</li>
        ))}
      </ul>
    </div>
  );
}

export function ItemDetailPane({ item, league, prefs, onClose }: ItemDetailPaneProps) {
  const tradeSearch = useTradeSearch();
  const updatePrefs = useUpdatePrefs();
  const [localTolerance, setLocalTolerance] = useState<number | null>(null);
  const [copyFeedback, setCopyFeedback] = useState<string | null>(null);

  const priceQ = usePriceLookup(league, item ? [item] : []);
  const price = item ? priceQ.data?.prices?.[item.id] ?? null : null;

  if (!item) {
    return (
      <aside className="panel hidden h-full p-4 text-sm text-ink-500 lg:block">
        Select an item to see its details.
      </aside>
    );
  }

  const tolerance = localTolerance ?? prefs?.trade_tolerance_pct ?? 10;

  const onSearch = async (mode: "exact" | "upgrade") => {
    const result = await tradeSearch.mutateAsync({
      mode,
      item,
      league,
      tolerance_pct: mode === "exact" ? tolerance : undefined,
    });
    window.open(result.url, "_blank", "noopener,noreferrer");
    try {
      await navigator.clipboard?.writeText(JSON.stringify(result.payload, null, 2));
      setCopyFeedback("search JSON copied to clipboard");
    } catch {
      setCopyFeedback("could not copy; see console");
      console.info("trade search payload", result.payload);
    }
    setTimeout(() => setCopyFeedback(null), 3500);
  };

  const onPersistTolerance = () => {
    if (localTolerance == null) return;
    updatePrefs.mutate({ trade_tolerance_pct: localTolerance });
  };

  return (
    <aside className="panel flex h-full flex-col gap-3 p-4 text-sm" aria-label="Item details">
      <header className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          {item.name && <div className="font-display text-base">{item.name}</div>}
          <div className="truncate text-parchment-100/80">{item.type_line}</div>
        </div>
        <div className="flex flex-col items-end gap-1 text-[11px] uppercase tracking-wide text-ink-500">
          <span>{item.rarity}</span>
          {item.ilvl != null && <span>ilvl {item.ilvl}</span>}
          {item.corrupted && <span className="text-red-400">corrupted</span>}
          {price && (
            <PriceBadge
              price={price}
              threshold={prefs?.valuable_threshold_chaos}
            />
          )}
          {onClose && (
            <button type="button" onClick={onClose} className="mt-1 text-ember-400">
              close
            </button>
          )}
        </div>
      </header>

      {item.properties.length > 0 && (
        <ul className="text-sm text-parchment-100/90">
          {item.properties.map((property, idx) => (
            <li key={`prop-${idx}`}>
              <span className="text-ink-500">{property.name}:</span>{" "}
              <span>{property.value ?? "—"}</span>
            </li>
          ))}
        </ul>
      )}

      {item.requirements.length > 0 && (
        <div className="text-xs text-ink-500">
          Requires{" "}
          {item.requirements
            .map((r) => `${r.value ?? "?"} ${r.name}`)
            .join(", ")}
        </div>
      )}

      <ModSection title="Enchant" mods={item.enchant_mods} tone="text-rarity-rare" />
      <ModSection title="Implicit" mods={item.implicit_mods} tone="text-rarity-magic" />
      <ModSection title="Rune" mods={item.rune_mods} tone="text-rarity-gem" />
      <ModSection title="Explicit" mods={item.explicit_mods} tone="text-rarity-magic" />
      <ModSection title="Crafted" mods={item.crafted_mods} tone="text-rarity-unique" />

      <div className="mt-auto space-y-2 border-t border-ink-700 pt-3">
        <div className="flex items-center gap-2 text-xs">
          <label htmlFor="tolerance" className="text-ink-500">
            Exact tolerance
          </label>
          <input
            id="tolerance"
            type="number"
            min={0}
            max={200}
            value={tolerance}
            onChange={(event) =>
              setLocalTolerance(Number.parseInt(event.target.value, 10) || 0)
            }
            className="w-16 rounded-md border border-ink-600 bg-ink-800 px-2 py-1 text-right"
          />
          <span className="text-ink-500">%</span>
          <button
            type="button"
            onClick={onPersistTolerance}
            className="ml-auto btn-ghost text-xs"
            disabled={localTolerance == null || updatePrefs.isPending}
          >
            save
          </button>
        </div>
        <div className="flex flex-col gap-2 sm:flex-row">
          <button
            type="button"
            className="btn-primary flex-1"
            onClick={() => onSearch("exact")}
            disabled={tradeSearch.isPending}
          >
            Same item on trade
          </button>
          <button
            type="button"
            className="btn-ghost flex-1"
            onClick={() => onSearch("upgrade")}
            disabled={tradeSearch.isPending}
          >
            Upgrade search
          </button>
        </div>
        {copyFeedback && <p className="text-xs text-ember-400">{copyFeedback}</p>}
        <p className="text-[11px] text-ink-500">
          Opens PoE2 Trade for this league and copies the search JSON to your
          clipboard. Full auto-prefill will be enabled once the GGG trade API
          client is wired.
        </p>
      </div>
    </aside>
  );
}
