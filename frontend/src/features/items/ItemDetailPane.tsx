import { useState } from "react";

import {
  useCreateShare,
  useCurrencyRates,
  useItemText,
  usePriceLookup,
  useRefinedPriceEstimate,
  useRevokeShare,
  useTradeSearch,
  useUpdatePrefs,
  shareViewPath,
} from "@/api/hooks";
import { CharacterPaneGothicBackdrop } from "@/features/characters/CharacterPaneGothicBackdrop";
import { useIsItemPriceInflight } from "@/features/pricing/priceInflightContext";
import { ItemImageExportActions } from "@/features/items/ItemImageExport";
import { splitExplicitMods, usefulProperties } from "@/features/items/itemPaneModel";
import {
  ExplicitModLine,
  ModDivider,
  ModSection,
  ModText,
  PANE_SECTION_HEADING,
} from "@/features/items/ItemModPresentation";
import { paneBorderColor, RARITY_NAME_CLASS, isRuneforgedItem, runeforgedBorderClass } from "@/features/items/itemVisualStyles";
import type { Item, ItemRarity, Prefs } from "@/api/types";
import { copyTextToClipboard } from "@/utils/clipboard";

import {
  computeItemScore,
  currencyRatesToChaosPair,
} from "./itemMetrics";
import { itemRollScoreState } from "./modRollMetrics";
import { PercentBar } from "./PercentBar";
import { itemReferenceHasAggregate, itemReferenceRollPcts, uniqueTypeRollPercent } from "./uniqueReferenceRoll";
import { PriceBadge } from "./PriceBadge";
import { itemIconDisplayUrl } from "./itemRarityFavicon";
import {
  IconChevronsUp,
  IconClipboard,
  IconClose,
  IconLinkOff,
  IconLinkShare,
  IconSave,
  IconSearchExact,
} from "./itemPaneIcons";

export interface ItemDetailPaneProps {
  item: Item | null;
  league: string | null;
  prefs: Prefs | undefined;
  onClose?: () => void;
  /** In `public` mode, trade, PoE2 text, pricing, and share actions are hidden. */
  mode?: "app" | "public";
}

// ─── main component ───────────────────────────────────────────────────────────

export function ItemDetailPane({
  item,
  league,
  prefs,
  onClose,
  mode = "app",
}: ItemDetailPaneProps) {
  const isApp = mode === "app";
  const tradeSearch = useTradeSearch();
  const itemText = useItemText();
  const updatePrefs = useUpdatePrefs();
  const createShare = useCreateShare();
  const revokeShare = useRevokeShare();
  const [localTolerance, setLocalTolerance] = useState<number | null>(null);
  const [copyFeedback, setCopyFeedback] = useState<string | null>(null);
  const [shareFeedback, setShareFeedback] = useState<string | null>(null);
  const [lastShareId, setLastShareId] = useState<string | null>(null);
  const [pricingRerunState, setPricingRerunState] = useState<{ itemId: string | null; n: number }>({ itemId: null, n: 0 });
  // Derived synchronously: if the stored itemId doesn't match the current item, rerun is 0 this render.
  // This prevents the POST effect in useRefinedPriceEstimate from firing for a new item before
  // the previous useEffect-based reset could take effect (they shared the same React flush).
  const pricingRerun = pricingRerunState.itemId === (item?.id ?? null) ? pricingRerunState.n : 0;

  const priceQ = usePriceLookup(isApp ? league : null, isApp && item ? [item] : []);
  const price = isApp && item ? (priceQ.data?.prices?.[item.id] ?? null) : null;
  const priceInflight = useIsItemPriceInflight(isApp ? item?.id : undefined);
  const currencyRatesQ = useCurrencyRates(isApp ? league : null);
  const currencyChaos = currencyRatesToChaosPair(currencyRatesQ.data);
  const tradeTol = localTolerance ?? prefs?.trade_tolerance_pct ?? 10;
  const refinedQ = useRefinedPriceEstimate(
    isApp ? league : null,
    item,
    tradeTol,
    Boolean(isApp && league && item),
    pricingRerun,
    false,
  );

  const refinedPricingInProgress =
    priceInflight ||
    refinedQ.job?.status === "queued" ||
    refinedQ.job?.status === "running";

  const pricingBusy =
    priceQ.isFetching || currencyRatesQ.isFetching || refinedQ.isLoading || refinedPricingInProgress;

  const refreshPricingTitle = refinedPricingInProgress
    ? priceInflight
      ? "Price update already queued or running for this item"
      : "Pricing is already running or queued for this item"
    : pricingBusy
      ? "Refreshing…"
      : "Refresh pricing (quick lookup, rates, and refined estimate)";

  if (!item) {
    return (
      <aside className="relative panel hidden h-full overflow-hidden p-4 text-sm text-parchment-200/80 lg:block">
        <CharacterPaneGothicBackdrop className="rounded-md" />
        <p className="relative z-10">Select an item to see its details.</p>
      </aside>
    );
  }

  const tolerance = tradeTol;
  const visibleProps = usefulProperties(item.properties);
  const visibleReqs = usefulProperties(item.requirements);
  const { prefixes, suffixes } = splitExplicitMods(item.explicit_mods, item.rarity);
  const showPrefixSuffix =
    item.rarity === "Rare" || (item.rarity === "Magic" && item.explicit_mods.length >= 2);
  const gggRoll = itemRollScoreState(item);
  const typeRefPcts = itemReferenceRollPcts(item);
  const hasTypeRefRoll = itemReferenceHasAggregate(typeRefPcts);
  const hasGggRoll = gggRoll.showAggregate;
  const hasRollData = hasTypeRefRoll || hasGggRoll;
  const modPctsForScore = hasTypeRefRoll ? typeRefPcts : gggRoll.modPcts;
  const itemScore = hasRollData ? computeItemScore(modPctsForScore) : null;
  const showModRollHints = item.rarity !== "Unique";
  const refIm = item.implicit_mod_range_hints;
  const refEx = item.explicit_mod_range_hints;

  const nameClass = RARITY_NAME_CLASS[item.rarity as ItemRarity] ?? "";

  const onSearch = async (mode: "exact" | "upgrade" | "weighted_upgrade") => {
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

  const onCreateShare = async () => {
    if (!league?.trim()) {
      setShareFeedback("Select a league in the app header first.");
      setTimeout(() => setShareFeedback(null), 4000);
      return;
    }
    try {
      const { share_id: sid } = await createShare.mutateAsync({ league, item });
      setLastShareId(sid);
      const href = `${window.location.origin}${shareViewPath(sid)}`;
      await copyTextToClipboard(href);
      setShareFeedback("Public link copied to clipboard");
    } catch {
      setShareFeedback("Could not create share (rate limit or server error).");
    }
    setTimeout(() => setShareFeedback(null), 4000);
  };

  const onRevokeShare = async () => {
    if (!lastShareId) return;
    try {
      await revokeShare.mutateAsync({ shareId: lastShareId });
      setLastShareId(null);
      setShareFeedback("Link revoked");
    } catch {
      setShareFeedback("Could not revoke link");
    }
    setTimeout(() => setShareFeedback(null), 4000);
  };

  const onRefreshPricing = () => {
    if (priceInflight || refinedPricingInProgress) return;
    void priceQ.refetch();
    void currencyRatesQ.refetch();
    setPricingRerunState((prev) => ({
      itemId: item?.id ?? null,
      n: prev.itemId === (item?.id ?? null) ? prev.n + 1 : 1,
    }));
  };

  const borderCol = paneBorderColor(item);
  const runeforged = isRuneforgedItem(item);
  const flavour =
    item.flavour_text?.trim() || item.flavourText?.trim() || item.flavorText?.trim() || "";

  return (
    <aside
      className="panel relative flex h-full min-h-0 flex-col gap-3 overflow-y-auto p-4 text-sm ring-1 ring-amber-200/10"
      style={{
        borderWidth: 1,
        borderColor: borderCol,
        background: "linear-gradient(180deg, rgba(22,20,16,0.75) 0%, rgba(8,8,10,0.97) 100%)",
        boxShadow: "inset 0 1px 0 rgba(212,168,60,0.12), 0 0 20px rgba(0,0,0,0.4)",
      }}
      aria-label={isApp ? "Item details" : "Shared item"}
    >
      {/* ── Header ── */}
      <header className="flex items-start gap-3">
        {/* Item icon */}
        <div
          className={[
            "flex shrink-0 items-center justify-center rounded border bg-ink-950/60 p-1",
            runeforged ? runeforgedBorderClass : "border-ink-700",
          ].join(" ")}
        >
          <img
            src={itemIconDisplayUrl(item)}
            alt={item.name || item.type_line}
            className="object-contain"
            style={{ width: item.w * 32, height: item.h * 32, maxWidth: 96, maxHeight: 96 }}
            loading="lazy"
            onError={(e) => {
              (e.currentTarget as HTMLImageElement).parentElement!.style.display = "none";
            }}
          />
        </div>
        <div className="min-w-0 flex-1">
          {item.name && (
            <div className={`break-words font-display text-base leading-snug ${nameClass}`}>
              {item.name}
            </div>
          )}
          <div className="break-words text-parchment-100/80">{item.type_line}</div>
          <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-0.5 text-[11px] uppercase tracking-wide text-parchment-200/85">
            <span>{item.rarity}</span>
            {item.ilvl != null && <span>ilvl {item.ilvl}</span>}
            {item.corrupted && <span className="text-red-400">corrupted</span>}
          </div>
          {isApp && league && (
            <div className="mt-1 flex flex-wrap items-center gap-1.5">
              {refinedPricingInProgress ? (
                <span className="inline-flex items-center rounded border border-amber-500/50 bg-amber-950/50 px-1.5 py-0.5 text-[11px] font-medium text-amber-100/95">
                  {refinedQ.job?.status === "running" ? "Updating price…" : "Price queued…"}
                </span>
              ) : price ? (
                <PriceBadge
                  price={price}
                  threshold={prefs?.valuable_threshold_chaos}
                  currencyChaos={currencyChaos}
                />
              ) : refinedQ.job?.status === "completed" &&
                refinedQ.job.result &&
                (refinedQ.job.result.estimate_method === "trade_median" ||
                  refinedQ.job.result.estimate_method === "poe2scout") ? (
                <PriceBadge
                  price={refinedQ.job.result}
                  threshold={prefs?.valuable_threshold_chaos}
                  currencyChaos={currencyChaos}
                />
              ) : (
                <span className="text-[11px] text-ui-muted">No price available</span>
              )}
              <button
                type="button"
                onClick={onRefreshPricing}
                disabled={pricingBusy}
                className="inline-flex h-6 w-6 shrink-0 items-center justify-center rounded border border-ink-600 bg-ink-900/80 text-parchment-200/90 transition hover:border-ember-500/50 hover:text-ember-200 disabled:cursor-not-allowed disabled:opacity-40"
                title={refreshPricingTitle}
                aria-label="Refresh pricing for this item"
              >
                <RefreshPricingIcon
                  className={pricingBusy ? "animate-spin" : undefined}
                />
              </button>
            </div>
          )}
          {isApp && league && refinedPricingInProgress && (
            <p
              className="mt-1.5 rounded border border-amber-500/35 bg-amber-950/35 px-2 py-1.5 text-[11px] leading-snug text-amber-100/90"
              role="status"
              aria-live="polite"
            >
              A hybrid price check is already queued for this item
              {refinedQ.job?.status === "running" ? " and is running now" : ""}. The refresh
              button stays disabled until it finishes.
            </p>
          )}
          {isApp && league && !refinedPricingInProgress && (
            <div className="mt-1 space-y-0.5 text-[11px] text-parchment-100/85">
              {refinedQ.job?.status === "failed" && (
                <span className="text-amber-300/90">Refined estimate unavailable (try again later)</span>
              )}
            </div>
          )}
        </div>
        {isApp && onClose && (
          <button
            type="button"
            onClick={onClose}
            className="inline-flex shrink-0 items-center justify-center rounded-md p-1 text-ember-400 transition hover:bg-ink-800/80 hover:text-ember-300"
            aria-label="Close item details"
          >
            <IconClose />
          </button>
        )}
      </header>

      {flavour ? (
        <blockquote
          className={`whitespace-pre-line border-l-2 pl-3 font-display text-sm italic leading-relaxed ${
            item.rarity === "Unique"
              ? "border-amber-500/70 text-amber-100/95"
              : "border-ink-600 text-parchment-200/90"
          }`}
        >
          {flavour}
        </blockquote>
      ) : null}
      {/* ── Item quality score (implicits + explicits with roll data) ── */}
      {hasRollData && itemScore != null && (
        <div className="flex items-center gap-2 text-xs">
          <span
            className={`shrink-0 ${PANE_SECTION_HEADING}`}
            title={
              hasTypeRefRoll
                ? "Mean of per-mod type quality (0% = min end of wiki range, 100% = best). Excludes lines without a parseable range."
                : "Mean of per-mod roll% (T1% when known, else tier roll)"
            }
          >
            {hasTypeRefRoll ? "Item quality" : "Item score"}
          </span>
          <div className="min-w-0 flex-1">
            <PercentBar pct={itemScore} showValue size="md" />
          </div>
        </div>
      )}

      {/* ── Item stats (Physical Damage, APS, Armour …) ── */}
      {visibleProps.length > 0 && (
        <div>
          <h4 className={PANE_SECTION_HEADING}>Stats</h4>
          <ul className="mt-1 space-y-0.5 text-sm text-parchment-100/90">
            {visibleProps.map((p, idx) => (
               
              <li
                key={idx}
                className="flex justify-between gap-2 border-b border-ink-800/30 pb-0.5 last:border-b-0"
              >
                <span className="shrink-0 text-parchment-200/80">{p.name}</span>
                <span className="min-w-0 text-right font-mono text-[13px] font-semibold tabular-nums">
                  <ModText raw={p.value!} />
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* ── Requirements ── */}
      {visibleReqs.length > 0 && (
        <div className="text-xs text-parchment-100/80">
          Requires {visibleReqs.map((r) => `${r.value} ${r.name}`).join(", ")}
        </div>
      )}

      {/* ── Sockets ── */}
      {item.sockets.length > 0 && (
        <div className="flex items-center gap-1.5">
          <span className={PANE_SECTION_HEADING}>Sockets</span>
          {item.sockets.map((s, idx) => (
            <span
               
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
      {item.implicit_mods.length > 0 && (
        <div>
          <h4 className={PANE_SECTION_HEADING}>Implicit</h4>
          <ul className="mt-1 list-none space-y-2.5 text-rarity-magic">
            {item.implicit_mods.map((mod, idx) => (
              <ExplicitModLine
                 
                key={idx}
                mod={mod}
                detail={item.implicit_mod_details[idx]}
                showRollHints={showModRollHints}
                referenceRangeText={refIm?.[idx] ?? null}
                typeRollPercent={uniqueTypeRollPercent(mod, refIm?.[idx] ?? null)}
              />
            ))}
          </ul>
        </div>
      )}
      <ModSection title="Rune" mods={item.rune_mods} tone="text-rarity-gem" />

      {/* ── Socketed items (runes, soul cores) ── */}
      {item.socketed_items.length > 0 && (
        <div>
          <h4 className={PANE_SECTION_HEADING}>Runes &amp; Cores</h4>
          <ul className="mt-1 space-y-2">
            {item.socketed_items.map((si) => (
              <li key={si.id} className="rounded border border-ink-600 bg-ink-800/60 px-2 py-1.5">
                <div className="text-xs font-semibold text-rarity-currency">
                  {si.type_line || si.name}
                </div>
                {si.explicit_mods.length > 0 && (
                  <ul className="mt-0.5 space-y-0.5 text-[11px] text-parchment-100/70">
                    {si.explicit_mods.map((mod, idx) => (
                       
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
                  <h4 className={PANE_SECTION_HEADING}>Prefixes</h4>
                  <ul className="mt-1 list-none space-y-2.5 text-rarity-magic">
                    {prefixes.map((mod, idx) => (
                      <ExplicitModLine
                         
                        key={idx}
                        mod={mod}
                        detail={item.explicit_mod_details[idx]}
                        showRollHints={showModRollHints}
                        referenceRangeText={refEx?.[idx] ?? null}
                        typeRollPercent={uniqueTypeRollPercent(mod, refEx?.[idx] ?? null)}
                      />
                    ))}
                  </ul>
                </div>
              )}
              {prefixes.length > 0 && suffixes.length > 0 && <ModDivider />}
              {suffixes.length > 0 && (
                <div>
                  <h4 className={PANE_SECTION_HEADING}>Suffixes</h4>
                  <ul className="mt-1 list-none space-y-2.5 text-sm text-rarity-magic">
                    {suffixes.map((mod, idx) => (
                      <ExplicitModLine
                         
                        key={idx}
                        mod={mod}
                        detail={item.explicit_mod_details[prefixes.length + idx]}
                        showRollHints={showModRollHints}
                        referenceRangeText={refEx?.[prefixes.length + idx] ?? null}
                        typeRollPercent={uniqueTypeRollPercent(
                          mod,
                          refEx?.[prefixes.length + idx] ?? null,
                        )}
                      />
                    ))}
                  </ul>
                </div>
              )}
            </>
          ) : (
            <div>
              <h4 className={PANE_SECTION_HEADING}>
                {item.rarity === "Unique" ? "Unique mods" : "Mods"}
              </h4>
              <ul
                className={`mt-1 list-none space-y-2.5 text-sm ${
                  item.rarity === "Unique" ? "text-rarity-unique" : "text-rarity-magic"
                }`}
              >
                {item.explicit_mods.map((mod, idx) => (
                  <ExplicitModLine
                     
                    key={idx}
                    mod={mod}
                    detail={item.explicit_mod_details[idx]}
                    showRollHints={showModRollHints}
                    referenceRangeText={refEx?.[idx] ?? null}
                    typeRollPercent={uniqueTypeRollPercent(mod, refEx?.[idx] ?? null)}
                  />
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      <ModSection title="Crafted" mods={item.crafted_mods} tone="text-rarity-unique" />

      {isApp && (
        <div className="shrink-0 space-y-2 border-t border-ink-700 pt-3">
          <h4 className={PANE_SECTION_HEADING}>Public link</h4>
          <p className="text-[11px] text-parchment-100/85">
            Creates a read-only page anyone can open. No GGG account or app login is required to
            view the snapshot.
          </p>
          <div className="flex flex-col gap-2">
            <button
              type="button"
              className="btn-ghost inline-flex w-full items-center justify-center gap-2 text-center text-xs"
              onClick={() => void onCreateShare()}
              disabled={createShare.isPending}
            >
              <IconLinkShare />
              <span>Create &amp; copy link</span>
            </button>
            {lastShareId && (
              <button
                type="button"
                className="btn-ghost inline-flex w-full items-center justify-center gap-2 text-center text-xs"
                onClick={() => void onRevokeShare()}
                disabled={revokeShare.isPending}
              >
                <IconLinkOff />
                <span>Revoke link</span>
              </button>
            )}
          </div>
          {shareFeedback && <p className="text-xs text-ember-400">{shareFeedback}</p>}
        </div>
      )}

      {isApp && (
        <div className="shrink-0">
          <ItemImageExportActions
            item={item}
            priceSnapshot={
              league
                ? {
                    quickPrice: price,
                    currencyChaos,
                    valuableThresholdChaos: prefs?.valuable_threshold_chaos,
                    refinedJob: refinedQ.job,
                  }
                : undefined
            }
          />
        </div>
      )}

      {isApp && (
        <>
          <div className="shrink-0 border-t border-ink-700 pt-3">
            <button
              type="button"
              className="btn-ghost inline-flex w-full items-center justify-center gap-2 text-center text-sm"
              onClick={() => void onCopyItemText()}
              disabled={itemText.isPending}
            >
              <IconClipboard />
              <span>Copy PoE2 item text</span>
            </button>
          </div>

          <div className="shrink-0 space-y-2 border-t border-ink-700 pt-3">
            <div className="flex items-center gap-2 text-xs">
              <label htmlFor="tolerance" className="text-parchment-200/90">
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
              <span className="text-parchment-200/85">%</span>
              <button
                type="button"
                onClick={onPersistTolerance}
                className="ml-auto inline-flex min-w-[4.25rem] items-center justify-center gap-1.5 btn-ghost text-xs"
                disabled={localTolerance == null || updatePrefs.isPending}
              >
                <IconSave />
                <span>save</span>
              </button>
            </div>
            <div className="flex flex-col gap-2">
              <button
                type="button"
                className="btn-primary inline-flex w-full items-center justify-center gap-2 text-center"
                onClick={() => onSearch("exact")}
                disabled={tradeSearch.isPending}
              >
                <IconSearchExact />
                <span>Trade Search</span>
              </button>
              <div className="flex gap-2">
                <button
                  type="button"
                  className="btn-ghost inline-flex flex-1 items-center justify-center gap-2 text-center"
                  onClick={() => onSearch("upgrade")}
                  disabled={tradeSearch.isPending}
                  title="Hard min-value filters per stat (≥95% of current roll)"
                >
                  <IconChevronsUp />
                  <span>Upgrade</span>
                </button>
                <button
                  type="button"
                  className="btn-ghost inline-flex flex-1 items-center justify-center gap-2 text-center"
                  onClick={() => onSearch("weighted_upgrade")}
                  disabled={tradeSearch.isPending}
                  title="Weighted sum filter — T1 stats count more; finds items that are better overall"
                >
                  <IconChevronsUp />
                  <span>Upgrade (weighted)</span>
                </button>
              </div>
            </div>
            {copyFeedback && <p className="text-xs text-ember-400">{copyFeedback}</p>}
            <p className="text-[11px] text-parchment-100/85">
              Opens PoE2 Trade for this league and copies the search JSON to your clipboard.
            </p>
          </div>
        </>
      )}
    </aside>
  );
}

function RefreshPricingIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      width="14"
      height="14"
      viewBox="0 0 24 24"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
    >
      <path d="M23 4v6h-6" />
      <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10" />
    </svg>
  );
}
