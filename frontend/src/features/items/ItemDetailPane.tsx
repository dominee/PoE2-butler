import { useState } from "react";

import { useItemText, usePriceLookup, useTradeSearch, useUpdatePrefs } from "@/api/hooks";
import { ItemImageExportActions } from "@/features/items/ItemImageExport";
import { splitExplicitMods, usefulProperties } from "@/features/items/itemPaneModel";
import {
  ExplicitModLine,
  ModDivider,
  ModSection,
  ModText,
  modQuality,
} from "@/features/items/ItemModPresentation";
import { PANE_RARITY_BORDER, RARITY_NAME_CLASS } from "@/features/items/itemVisualStyles";
import type { Item, ItemRarity, Prefs } from "@/api/types";
import { copyTextToClipboard } from "@/utils/clipboard";

import { PercentBar, computeItemScore } from "./PercentBar";
import { PriceBadge } from "./PriceBadge";

export interface ItemDetailPaneProps {
  item: Item | null;
  league: string | null;
  prefs: Prefs | undefined;
  onClose?: () => void;
}

// ─── main component ───────────────────────────────────────────────────────────

export function ItemDetailPane({ item, league, prefs, onClose }: ItemDetailPaneProps) {
  const tradeSearch = useTradeSearch();
  const itemText = useItemText();
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
  const hasTierData = item.explicit_mod_details.some((d) => d.tier != null);

  // Per-mod quality percentages and item score
  const modPcts = item.explicit_mods.map((mod, idx) =>
    modQuality(mod, item.explicit_mod_details[idx]),
  );
  const itemScore = hasTierData ? computeItemScore(modPcts) : null;

  const nameClass = RARITY_NAME_CLASS[item.rarity as ItemRarity] ?? "";

  const onSearch = async (mode: "exact" | "upgrade") => {
    const result = await tradeSearch.mutateAsync({
      mode,
      item,
      league,
      tolerance_pct: mode === "exact" ? tolerance : undefined,
    });
    window.open(result.url, "_blank", "noopener,noreferrer");
    try {
      await copyTextToClipboard(JSON.stringify(result.payload, null, 2));
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

  const onCopyItemText = async () => {
    try {
      const { text } = await itemText.mutateAsync({ item });
      await copyTextToClipboard(text);
      setCopyFeedback("PoE2 item text copied to clipboard");
    } catch {
      setCopyFeedback("could not copy item text");
    }
    setTimeout(() => setCopyFeedback(null), 3500);
  };

  return (
    <aside
      className="panel flex h-full min-h-0 flex-col gap-3 overflow-y-auto p-4 text-sm"
      style={{ borderColor: PANE_RARITY_BORDER[item.rarity as ItemRarity] }}
      aria-label="Item details"
    >
      {/* ── Header ── */}
      <header className="flex items-start gap-3">
        {/* Item icon */}
        {item.icon && (
          <div className="flex shrink-0 items-center justify-center rounded border border-ink-700 bg-ink-950/60 p-1">
            <img
              src={item.icon}
              alt={item.name || item.type_line}
              className="object-contain"
              style={{ width: item.w * 32, height: item.h * 32, maxWidth: 96, maxHeight: 96 }}
              loading="lazy"
              onError={(e) => {
                (e.currentTarget as HTMLImageElement).parentElement!.style.display = "none";
              }}
            />
          </div>
        )}
        <div className="min-w-0 flex-1">
          {item.name && (
            <div className={`break-words font-display text-base leading-snug ${nameClass}`}>
              {item.name}
            </div>
          )}
          <div className="break-words text-parchment-100/80">{item.type_line}</div>
          <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-0.5 text-[11px] uppercase tracking-wide text-ink-500">
            <span>{item.rarity}</span>
            {item.ilvl != null && <span>ilvl {item.ilvl}</span>}
            {item.corrupted && <span className="text-red-400">corrupted</span>}
          </div>
          {price && (
            <div className="mt-1">
              <PriceBadge price={price} threshold={prefs?.valuable_threshold_chaos} />
            </div>
          )}
        </div>
        {onClose && (
          <button type="button" onClick={onClose} className="shrink-0 text-ember-400 text-sm">
            ✕
          </button>
        )}
      </header>

      {/* ── Item quality score ── */}
      {hasTierData && (
        <div className="flex items-center gap-2 text-xs">
          <span className="shrink-0 text-[10px] uppercase tracking-widest text-ink-500">
            Item score
          </span>
          <div className="flex-1">
            <PercentBar pct={itemScore} showValue />
          </div>
        </div>
      )}

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
                <span className="text-right font-semibold text-parchment-50">
                  <ModText raw={p.value!} />
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* ── Requirements ── */}
      {visibleReqs.length > 0 && (
        <div className="text-xs text-ink-500">
          Requires {visibleReqs.map((r) => `${r.value} ${r.name}`).join(", ")}
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

      {/* ── Socketed items (runes, soul cores) ── */}
      {item.socketed_items.length > 0 && (
        <div>
          <h4 className="text-[10px] font-semibold uppercase tracking-widest text-ink-500">
            Runes &amp; Cores
          </h4>
          <ul className="mt-1 space-y-2">
            {item.socketed_items.map((si) => (
              <li key={si.id} className="rounded border border-ink-600 bg-ink-800/60 px-2 py-1.5">
                <div className="text-xs font-semibold text-rarity-currency">
                  {si.type_line || si.name}
                </div>
                {si.explicit_mods.length > 0 && (
                  <ul className="mt-0.5 space-y-0.5 text-[11px] text-parchment-100/70">
                    {si.explicit_mods.map((mod, idx) => (
                      // eslint-disable-next-line react/no-array-index-key
                      <li key={idx} className="break-words leading-snug">
                        <ModText raw={mod} />
                      </li>
                    ))}
                  </ul>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* ── Explicit mods: prefix / suffix split with optional tier badges ── */}
      {item.explicit_mods.length > 0 && (
        <div className="space-y-1">
          {showPrefixSuffix ? (
            <>
              {prefixes.length > 0 && (
                <div>
                  <h4 className="text-[10px] font-semibold uppercase tracking-widest text-ink-500">
                    Prefixes
                  </h4>
                  <ul className="mt-1 space-y-0.5 text-sm text-rarity-magic">
                    {prefixes.map((mod, idx) => (
                      <ExplicitModLine
                        // eslint-disable-next-line react/no-array-index-key
                        key={idx}
                        mod={mod}
                        detail={hasTierData ? item.explicit_mod_details[idx] : undefined}
                      />
                    ))}
                  </ul>
                </div>
              )}
              {prefixes.length > 0 && suffixes.length > 0 && <ModDivider />}
              {suffixes.length > 0 && (
                <div>
                  <h4 className="text-[10px] font-semibold uppercase tracking-widest text-ink-500">
                    Suffixes
                  </h4>
                  <ul className="mt-1 space-y-0.5 text-sm text-rarity-magic">
                    {suffixes.map((mod, idx) => (
                      <ExplicitModLine
                        // eslint-disable-next-line react/no-array-index-key
                        key={idx}
                        mod={mod}
                        detail={
                          hasTierData
                            ? item.explicit_mod_details[prefixes.length + idx]
                            : undefined
                        }
                      />
                    ))}
                  </ul>
                </div>
              )}
            </>
          ) : (
            <div>
              <h4 className="text-[10px] font-semibold uppercase tracking-widest text-ink-500">
                {item.rarity === "Unique" ? "Unique mods" : "Mods"}
              </h4>
              <ul
                className={`mt-1 space-y-0.5 text-sm ${
                  item.rarity === "Unique" ? "text-rarity-unique" : "text-rarity-magic"
                }`}
              >
                {item.explicit_mods.map((mod, idx) => (
                  <ExplicitModLine
                    // eslint-disable-next-line react/no-array-index-key
                    key={idx}
                    mod={mod}
                    detail={hasTierData ? item.explicit_mod_details[idx] : undefined}
                  />
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      <ModSection title="Crafted" mods={item.crafted_mods} tone="text-rarity-unique" />

      <div className="shrink-0">
        <ItemImageExportActions item={item} />
      </div>

      <div className="shrink-0 border-t border-ink-700 pt-3">
        <button
          type="button"
          className="btn-ghost w-full text-left text-sm"
          onClick={() => void onCopyItemText()}
          disabled={itemText.isPending}
        >
          Copy PoE2 item text
        </button>
      </div>

      {/* ── Trade controls ── */}
      <div className="shrink-0 space-y-2 border-t border-ink-700 pt-3">
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
