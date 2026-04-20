import { useState } from "react";

import { usePriceLookup, useTradeSearch, useUpdatePrefs } from "@/api/hooks";
import type { Item, ItemProperty, Prefs } from "@/api/types";

import { PriceBadge } from "./PriceBadge";

export interface ItemDetailPaneProps {
  item: Item | null;
  league: string | null;
  prefs: Prefs | undefined;
  onClose?: () => void;
}

// --- sub-components --------------------------------------------------------

function ModList({ mods, tone }: { mods: string[]; tone: string }) {
  return (
    <ul className={`mt-1 space-y-0.5 text-sm ${tone}`}>
      {mods.map((mod, idx) => (
        // eslint-disable-next-line react/no-array-index-key
        <li key={idx} className="break-words leading-snug">
          {mod}
        </li>
      ))}
    </ul>
  );
}

function ModSection({ title, mods, tone }: { title: string; mods: string[]; tone: string }) {
  if (mods.length === 0) return null;
  return (
    <div>
      <h4 className="text-[10px] font-semibold uppercase tracking-widest text-ink-500">
        {title}
      </h4>
      <ModList mods={mods} tone={tone} />
    </div>
  );
}

/** Divider styled like the in-game item tooltip separator. */
function ModDivider() {
  return <div className="my-0.5 border-t border-ink-600/60" />;
}

/**
 * For Rare items the GGG API orders mods: prefixes first (≤3), suffixes last
 * (≤3).  For Magic items there is at most 1 prefix + 1 suffix.  We use the
 * positional convention to split visually; no mod-database lookup is required.
 */
function splitExplicitMods(
  mods: string[],
  rarity: string,
): { prefixes: string[]; suffixes: string[] } {
  if (mods.length === 0) return { prefixes: [], suffixes: [] };

  if (rarity === "Rare") {
    const boundary = Math.min(3, mods.length);
    return { prefixes: mods.slice(0, boundary), suffixes: mods.slice(boundary) };
  }
  if (rarity === "Magic" && mods.length >= 2) {
    return { prefixes: [mods[0]], suffixes: mods.slice(1) };
  }
  // Normal / Unique / Currency / Gem — show all together under "Mods"
  return { prefixes: mods, suffixes: [] };
}

/** Properties whose `values` array is empty are category headers (e.g. "Amulet",
 *  "Bow").  We skip them — the item header already shows the type. */
function usefulProperties(props: ItemProperty[]): ItemProperty[] {
  return props.filter((p) => p.value != null && p.value !== "");
}

// --- main component --------------------------------------------------------

export function ItemDetailPane({ item, league, prefs, onClose }: ItemDetailPaneProps) {
  const tradeSearch = useTradeSearch();
  const updatePrefs = useUpdatePrefs();
  const [localTolerance, setLocalTolerance] = useState<number | null>(null);
  const [copyFeedback, setCopyFeedback] = useState<string | null>(null);

  const priceQ = usePriceLookup(league, item ? [item] : []);
  const price = item ? (priceQ.data?.prices?.[item.id] ?? null) : null;

  if (!item) {
    return (
      <aside className="panel hidden h-full p-4 text-sm text-ink-500 lg:block">
        Select an item to see its details.
      </aside>
    );
  }

  const tolerance = localTolerance ?? prefs?.trade_tolerance_pct ?? 10;
  const visibleProps = usefulProperties(item.properties);
  const visibleReqs = usefulProperties(item.requirements);
  const { prefixes, suffixes } = splitExplicitMods(item.explicit_mods, item.rarity);
  const showPrefixSuffix =
    item.rarity === "Rare" || (item.rarity === "Magic" && item.explicit_mods.length >= 2);

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
    <aside
      className="panel flex h-full flex-col gap-3 overflow-y-auto p-4 text-sm"
      aria-label="Item details"
    >
      {/* ── Header ── */}
      <header className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          {item.name && (
            <div className="break-words font-display text-base leading-snug">{item.name}</div>
          )}
          <div className="break-words text-parchment-100/80">{item.type_line}</div>
        </div>
        <div className="flex shrink-0 flex-col items-end gap-1 text-[11px] uppercase tracking-wide text-ink-500">
          <span>{item.rarity}</span>
          {item.ilvl != null && <span>ilvl {item.ilvl}</span>}
          {item.corrupted && <span className="text-red-400">corrupted</span>}
          {price && (
            <PriceBadge price={price} threshold={prefs?.valuable_threshold_chaos} />
          )}
          {onClose && (
            <button type="button" onClick={onClose} className="mt-1 text-ember-400">
              close
            </button>
          )}
        </div>
      </header>

      {/* ── Item stats (Physical Damage, APS, Armour …) ── */}
      {visibleProps.length > 0 && (
        <div>
          <h4 className="text-[10px] font-semibold uppercase tracking-widest text-ink-500">
            Stats
          </h4>
          <ul className="mt-1 space-y-0.5 text-sm text-parchment-100/90">
            {visibleProps.map((p, idx) => (
              // eslint-disable-next-line react/no-array-index-key
              <li key={idx} className="flex justify-between gap-2">
                <span className="text-ink-500">{p.name}</span>
                <span className="text-right">{p.value}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* ── Requirements ── */}
      {visibleReqs.length > 0 && (
        <div className="text-xs text-ink-500">
          Requires{" "}
          {visibleReqs.map((r) => `${r.value} ${r.name}`).join(", ")}
        </div>
      )}

      {/* ── Sockets ── */}
      {item.sockets.length > 0 && (
        <div className="flex items-center gap-1.5">
          <span className="text-[10px] uppercase tracking-widest text-ink-500">Sockets</span>
          {item.sockets.map((s, idx) => (
            <span
              // eslint-disable-next-line react/no-array-index-key
              key={idx}
              className="inline-flex h-4 w-4 items-center justify-center rounded-full border border-ink-600 text-[9px] uppercase text-rarity-gem"
              title={s.type}
            >
              {s.type.slice(0, 1)}
            </span>
          ))}
        </div>
      )}

      {/* ── Enchant / Implicit / Rune ── */}
      <ModSection title="Enchant" mods={item.enchant_mods} tone="text-rarity-rare" />
      <ModSection title="Implicit" mods={item.implicit_mods} tone="text-rarity-magic" />
      <ModSection title="Rune" mods={item.rune_mods} tone="text-rarity-gem" />

      {/* ── Explicit mods: prefix / suffix split ── */}
      {item.explicit_mods.length > 0 && (
        <div className="space-y-1">
          {showPrefixSuffix ? (
            <>
              <ModSection title="Prefixes" mods={prefixes} tone="text-rarity-magic" />
              {prefixes.length > 0 && suffixes.length > 0 && <ModDivider />}
              <ModSection title="Suffixes" mods={suffixes} tone="text-rarity-magic" />
            </>
          ) : (
            <ModSection
              title={item.rarity === "Unique" ? "Unique mods" : "Mods"}
              mods={item.explicit_mods}
              tone={item.rarity === "Unique" ? "text-rarity-unique" : "text-rarity-magic"}
            />
          )}
        </div>
      )}

      <ModSection title="Crafted" mods={item.crafted_mods} tone="text-rarity-unique" />

      {/* ── Trade controls ── */}
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
          Opens PoE2 Trade for this league and copies the search JSON to your clipboard.
        </p>
      </div>
    </aside>
  );
}
