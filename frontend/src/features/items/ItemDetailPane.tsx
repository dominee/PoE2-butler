import { useState } from "react";

import { usePriceLookup, useTradeSearch, useUpdatePrefs } from "@/api/hooks";
import { ItemImageExportActions } from "@/features/items/ItemImageExport";
import type { Item, ItemProperty, ItemRarity, ModDetail, Prefs } from "@/api/types";
import { parseModParts } from "@/utils/modText";

import { PercentBar, computeItemScore } from "./PercentBar";
import { PriceBadge } from "./PriceBadge";

export interface ItemDetailPaneProps {
  item: Item | null;
  league: string | null;
  prefs: Prefs | undefined;
  onClose?: () => void;
}

// ─── rarity colour maps ──────────────────────────────────────────────────────

/** Inline border colour for the detail pane (overrides the panel base). */
const RARITY_BORDER: Partial<Record<ItemRarity, string>> = {
  Magic: "rgba(136,136,255,0.45)",
  Rare: "rgba(255,255,119,0.35)",
  Unique: "rgba(175,96,37,0.9)",
  Currency: "rgba(170,158,130,0.5)",
  Gem: "rgba(27,162,155,0.55)",
  DivinationCard: "rgba(100,100,100,0.4)",
};

/** Tailwind text class for the item name in the header. */
const RARITY_NAME_CLASS: Partial<Record<ItemRarity, string>> = {
  Magic: "text-rarity-magic",
  Rare: "text-rarity-rare",
  Unique: "text-rarity-unique",
  Gem: "text-rarity-gem",
  Currency: "text-rarity-currency",
};

// ─── tier badge ──────────────────────────────────────────────────────────────

function tierBadgeClass(tier: number): string {
  if (tier === 1) return "bg-amber-500/25 text-amber-300 border-amber-500/50";
  if (tier === 2) return "bg-yellow-600/20 text-yellow-300 border-yellow-500/40";
  if (tier <= 4) return "bg-lime-900/25 text-lime-400/80 border-lime-700/40";
  if (tier <= 6) return "bg-ink-600/60 text-ink-300 border-ink-500";
  return "bg-ink-700/60 text-ink-500 border-ink-600";
}

function TierBadge({ tier }: { tier: number }) {
  return (
    <span
      className={`inline-flex shrink-0 items-center rounded border px-1 py-px text-[9px] font-bold leading-none ${tierBadgeClass(tier)}`}
      title={`Tier ${tier}`}
    >
      T{tier}
    </span>
  );
}

// ─── mod text components ─────────────────────────────────────────────────────

/** Render a mod string with numeric values highlighted in parchment-50. */
function ModText({ raw }: { raw: string }) {
  const parts = parseModParts(raw);
  return (
    <span>
      {parts.map((part, i) =>
        part.isNum ? (
          // eslint-disable-next-line react/no-array-index-key
          <strong key={i} className="font-semibold text-parchment-50">
            {part.text}
          </strong>
        ) : (
          // eslint-disable-next-line react/no-array-index-key
          <span key={i}>{part.text}</span>
        ),
      )}
    </span>
  );
}

/**
 * Extract the dominant numeric value from a mod string for quality calculation.
 * Returns the absolute value of the first number found, or null.
 */
function extractModValue(modText: string): number | null {
  const parts = parseModParts(modText);
  const numPart = parts.find((p) => p.isNum);
  if (!numPart) return null;
  const n = parseFloat(numPart.text.replace("%", ""));
  return Number.isFinite(n) ? Math.abs(n) : null;
}

/** Roll quality: how well this roll sits within its tier range (0–100+). */
function rollQuality(value: number, min: number, max: number): number {
  if (max <= min) return 100;
  return Math.round(((value - min) / (max - min)) * 100);
}

/** Compute per-mod quality percentage from ModDetail if available.
 *
 * When `t1_max` is known (from bundled mod DB), returns the cross-tier
 * percentage: value / t1_max × 100 (can exceed 100%).
 * Otherwise falls back to within-tier quality.
 */
function modQuality(mod: string, detail: ModDetail | undefined): number | null {
  const mag = detail?.magnitudes?.[0];
  if (!mag) return null;
  const value = extractModValue(mod);
  if (value == null) return null;

  // Cross-tier: compare against T1 max from the bundled mod DB.
  if (mag.t1_max != null && mag.t1_max > 0) {
    return Math.round((value / mag.t1_max) * 100);
  }

  // Within-tier fallback.
  if (mag.min == null || mag.max == null) return null;
  return rollQuality(value, mag.min, mag.max);
}

/**
 * Renders one explicit mod line with an optional tier badge, roll range, and
 * quality bar.  `detail` comes from `item.explicit_mod_details[idx]` — may be
 * undefined when the GGG API didn't return extended mod data.
 */
function ExplicitModLine({
  mod,
  detail,
}: {
  mod: string;
  detail: ModDetail | undefined;
}) {
  const tier = detail?.tier ?? null;
  const mag = detail?.magnitudes?.[0];
  const hasRange = mag?.min != null && mag?.max != null && mag.min !== mag.max;
  const hasCrossTier = mag?.t1_max != null;
  const pct = modQuality(mod, detail);

  return (
    <li className="break-words leading-snug">
      <div className="flex items-start gap-1.5">
        {tier != null && <TierBadge tier={tier} />}
        <span className="min-w-0 flex-1">
          <ModText raw={mod} />
          {hasRange && (
            <span className="ml-1 text-[10px] text-ink-500">
              [{mag!.min}–{mag!.max}]
            </span>
          )}
          {hasCrossTier && (
            <span className="ml-1 text-[10px] text-parchment-100/40">
              T1 max: {mag!.t1_max}
            </span>
          )}
        </span>
      </div>
      {detail != null && (
        <PercentBar
          pct={pct}
          tierLabel={
            hasCrossTier
              ? `vs T1 max (${mag!.t1_max})`
              : tier != null
                ? `T${tier} roll quality`
                : undefined
          }
          showValue={pct != null}
        />
      )}
    </li>
  );
}

// ─── section helpers ─────────────────────────────────────────────────────────

function ModSection({ title, mods, tone }: { title: string; mods: string[]; tone: string }) {
  if (mods.length === 0) return null;
  return (
    <div>
      <h4 className="text-[10px] font-semibold uppercase tracking-widest text-ink-500">
        {title}
      </h4>
      <ul className={`mt-1 space-y-0.5 text-sm ${tone}`}>
        {mods.map((mod, idx) => (
          // eslint-disable-next-line react/no-array-index-key
          <li key={idx} className="break-words leading-snug">
            <ModText raw={mod} />
          </li>
        ))}
      </ul>
    </div>
  );
}

function ModDivider() {
  return <div className="my-0.5 border-t border-ink-600/50" />;
}

/**
 * PoE2 mod ordering: prefixes come first (≤3), suffixes follow (≤3).
 * We split at position 3 for Rare, at 1 for Magic.
 */
function splitExplicitMods(
  mods: string[],
  rarity: string,
): { prefixes: string[]; suffixes: string[] } {
  if (mods.length === 0) return { prefixes: [], suffixes: [] };
  if (rarity === "Rare") {
    const cut = Math.min(3, mods.length);
    return { prefixes: mods.slice(0, cut), suffixes: mods.slice(cut) };
  }
  if (rarity === "Magic" && mods.length >= 2) {
    return { prefixes: [mods[0]], suffixes: mods.slice(1) };
  }
  return { prefixes: mods, suffixes: [] };
}

/** Drop category-header properties (those with empty values, e.g. "Amulet"). */
function usefulProperties(props: ItemProperty[]): ItemProperty[] {
  return props.filter((p) => p.value != null && p.value !== "");
}

// ─── main component ───────────────────────────────────────────────────────────

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
      style={{ borderColor: RARITY_BORDER[item.rarity as ItemRarity] }}
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

      <ItemImageExportActions item={item} />

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
