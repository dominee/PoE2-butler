import { useRef, useState } from "react";
import { toPng } from "html-to-image";
import type { Item, ItemRarity, PriceEstimate, PriceJobState } from "@/api/types";

import { splitExplicitMods, usefulProperties } from "./itemPaneModel";
import { itemIconForExportPng } from "./itemRarityFavicon";
import { RARITY_NAME_CLASS } from "./itemVisualStyles";
import {
  type CurrencyChaosPair,
  computeItemScore,
} from "./itemMetrics";

import { itemRollScoreState } from "./modRollMetrics";
import { ExplicitModLine, GrantedSkillsSection, ModDivider, ModSection, ModText, PANE_SECTION_HEADING } from "./ItemModPresentation";
import { PercentBar } from "./PercentBar";
import { itemReferenceHasAggregate, itemReferenceRollPcts, uniqueTypeRollPercent } from "./uniqueReferenceRoll";
import { PriceBadge } from "./PriceBadge";
import { IconImageExport } from "./itemPaneIcons";
import { dataUrlToBlob } from "@/utils/pngExport";

/**
 * Optional pricing snapshot for PNG export; mirrors the item detail pane header.
 */
export interface ItemExportPriceSnapshot {
  quickPrice: PriceEstimate | null;
  currencyChaos: CurrencyChaosPair | null;
  valuableThresholdChaos?: number;
  refinedJob: PriceJobState | null;
}

/** Resolve the badge price using the same priority as the live detail pane header. */
function resolveBadgePrice(snap: ItemExportPriceSnapshot): PriceEstimate | null {
  if (snap.quickPrice) return snap.quickPrice;
  if (
    snap.refinedJob?.status === "completed" &&
    snap.refinedJob.result &&
    (snap.refinedJob.result.estimate_method === "trade_median" ||
      snap.refinedJob.result.estimate_method === "poe2scout")
  ) {
    return snap.refinedJob.result;
  }
  return null;
}

function errDetail(err: unknown): string {
  if (err instanceof Error) return err.message;
  return String(err);
}

/** Card border; matches export styling (not the live pane’s rgba border). */
const RARITY_CARD_BORDER: Record<ItemRarity, string> = {
  Normal: "border-ink-600",
  Magic: "border-rarity-magic/60",
  Rare: "border-rarity-rare/60",
  Unique: "border-rarity-unique/60",
  Currency: "border-rarity-currency/60",
  Gem: "border-rarity-gem/60",
  DivinationCard: "border-ink-600",
  QuestItem: "border-ink-600",
};

/**
 * Snapshot aligned with the item detail pane: same prefix/suffix split, tier
 * lines, and roll bars. `compact` omits “Runes & Cores” only. `detail` includes
 * socketed items and optional ``priceSnapshot`` (quick + refined estimates).
 */
/** Compact read-only item card for character export / detailed share views. */
export function ItemExportSnapshot({
  item,
  variant,
  priceSnapshot,
  showBranding = true,
  embedded = false,
}: {
  item: Item;
  variant: "compact" | "detail";
  priceSnapshot?: ItemExportPriceSnapshot | null;
  /** When false, omits the app title strip (character gear embeds). */
  showBranding?: boolean;
  /** Fit parent width instead of fixed 400px card (character export grid). */
  embedded?: boolean;
}) {
  const b = RARITY_CARD_BORDER[item.rarity] ?? "border-ink-600";
  const resolvedIcon = itemIconForExportPng(item);
  const nameClass = RARITY_NAME_CLASS[item.rarity as ItemRarity] ?? "";
  const widthClass = embedded ? "w-full max-w-full min-w-0 box-border" : "w-[400px]";
  const padClass = embedded ? "p-2 text-xs" : "p-3 text-sm";
  const iconScale = embedded ? 24 : 32;
  const iconMax = embedded ? 64 : 96;

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
  const showRunes = variant === "detail" && item.socketed_items.length > 0;
  const refIm = item.implicit_mod_range_hints;
  const refEx = item.explicit_mod_range_hints;
  const flavour =
    item.flavour_text?.trim() || item.flavourText?.trim() || item.flavorText?.trim() || "";

  return (
    <div
      className={`${b} ${widthClass} ${padClass} rounded-md border-2 bg-ink-900 text-left text-parchment-100 shadow-lg`}
    >
      {showBranding && (
        <div className="font-display text-sm font-semibold text-ember-200/90">PoE2 Hideout Butler</div>
      )}
      <div className={`flex items-start gap-2 ${showBranding ? "mt-2" : ""}`}>
        <div className="flex shrink-0 items-center justify-center rounded border border-ink-700 bg-ink-950/60 p-1">
          <img
            src={resolvedIcon}
            alt=""
            className="object-contain"
            style={{
              width: item.w * iconScale,
              height: item.h * iconScale,
              maxWidth: iconMax,
              maxHeight: iconMax,
            }}
          />
        </div>
        <div className="min-w-0">
          {item.name && (
            <div className={`break-words text-base font-display ${nameClass}`}>{item.name}</div>
          )}
          <div className="text-parchment-100/80">{item.type_line}</div>
          <div className="mt-1 text-[10px] uppercase text-parchment-200/85">
            <span>{item.rarity}</span>
            {item.ilvl != null && <span className="ml-1">ilvl {item.ilvl}</span>}
            {item.corrupted && <span className="ml-1 text-red-400">corrupted</span>}
          </div>
          {priceSnapshot && (() => {
            const p = resolveBadgePrice(priceSnapshot);
            return p ? (
              <div className="mt-1 flex flex-wrap items-center gap-1.5">
                <PriceBadge
                  price={p}
                  threshold={priceSnapshot.valuableThresholdChaos}
                  currencyChaos={priceSnapshot.currencyChaos}
                />
              </div>
            ) : null;
          })()}
        </div>
      </div>

      {hasRollData && itemScore != null && (
        <div className="mt-2 flex items-center gap-2 text-xs">
          <span className={`shrink-0 ${PANE_SECTION_HEADING}`}>
            {hasTypeRefRoll ? "Item quality" : "Item score"}
          </span>
          <div className="min-w-0 flex-1">
            <PercentBar pct={itemScore} showValue size="md" />
          </div>
        </div>
      )}

      {flavour ? (
        <blockquote className="mt-2 whitespace-pre-line border-l-2 border-amber-500/60 pl-2 font-display text-xs italic text-amber-100/90">
          {flavour}
        </blockquote>
      ) : null}

      {visibleProps.length > 0 && (
        <div className="mt-2">
          <h4 className={PANE_SECTION_HEADING}>Stats</h4>
          <ul className="mt-1 space-y-0.5 text-sm text-parchment-100/90">
            {visibleProps.map((p, idx) => (
               
              <li key={idx} className="flex justify-between gap-2">
                <span className="text-parchment-200/85">{p.name}</span>
                <span className="text-right font-semibold text-parchment-50">
                  {p.value != null ? <ModText raw={p.value} /> : null}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <GrantedSkillsSection skills={item.granted_skills ?? []} />

      {visibleReqs.length > 0 && (
        <div className="mt-1 text-xs text-parchment-200/85">
          Requires {visibleReqs.map((r) => `${r.value} ${r.name}`).join(", ")}
        </div>
      )}

      {item.sockets.length > 0 && (
        <div className="mt-1 flex items-center gap-1.5">
          <span className={PANE_SECTION_HEADING}>Sockets</span>
          {item.sockets.map((s, idx) => (
            <span
               
              key={idx}
              className="inline-flex h-4 w-4 items-center justify-center rounded-full border border-ink-600 text-[9px] uppercase text-rarity-gem"
            >
              {s.type.slice(0, 1)}
            </span>
          ))}
        </div>
      )}

      <div className="mt-1 space-y-1">
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
      </div>

      {showRunes && (
        <div className="mt-2">
          <h4 className={PANE_SECTION_HEADING}>Runes &amp; Cores</h4>
          <ul className="mt-1 space-y-2">
            {item.socketed_items.map((si) => (
              <li key={si.id} className="rounded border border-ink-600 bg-ink-800/60 px-2 py-1.5">
                <div className="text-xs font-semibold text-rarity-currency">
                  {si.type_line || si.name}
                </div>
                {(si.granted_skills?.length ?? 0) > 0 && (
                  <ul className="mt-0.5 space-y-0.5 text-[11px] text-rarity-gem">
                    {si.granted_skills!.map((skill, idx) => (
                      <li key={idx} className="break-words leading-snug">
                        {skill}
                      </li>
                    ))}
                  </ul>
                )}
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

      {item.explicit_mods.length > 0 && (
        <div className="mt-2 space-y-1">
          {showPrefixSuffix ? (
            <>
              {prefixes.length > 0 && (
                <div>
                  <h4 className={PANE_SECTION_HEADING}>Prefixes</h4>
                  <ul className="mt-1 space-y-0.5 text-sm text-rarity-magic">
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
                  <ul className="mt-1 space-y-0.5 text-sm text-rarity-magic">
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
                className={`mt-1 space-y-0.5 text-sm ${
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

      <div className="mt-1">
        <ModSection title="Crafted" mods={item.crafted_mods} tone="text-rarity-unique" />
      </div>
    </div>
  );
}

function downloadIconSvg() {
  return (
    <svg
      className="h-3.5 w-3.5 shrink-0"
      viewBox="0 0 20 20"
      fill="currentColor"
      aria-hidden
    >
      <path
        fillRule="evenodd"
        d="M3 17a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm3.293-7.707a1 1 0 011.414 0L9 10.586V3a1 1 0 112 0v7.586l1.293-1.293a1 1 0 111.414 1.414l-3 3a1 1 0 01-1.414 0l-3-3a1 1 0 010-1.414z"
        clipRule="evenodd"
      />
    </svg>
  );
}

export function ItemImageExportActions({
  item,
  priceSnapshot,
}: {
  item: Item;
  /** When set, detail PNG includes quick + refined pricing (same as the detail pane). */
  priceSnapshot?: ItemExportPriceSnapshot | null;
}) {
  const compactRef = useRef<HTMLDivElement>(null);
  const detailRef = useRef<HTMLDivElement>(null);
  const [msg, setMsg] = useState<string | null>(null);

  const baseName = `item-${item.id?.slice(0, 8) ?? "item"}`;

  const runCopy = async (r: React.RefObject<HTMLDivElement | null>, label: string) => {
    const el = r.current;
    if (!el) {
      setMsg("nothing to capture");
      return;
    }
    setMsg("rendering…");
    const secure = typeof window !== "undefined" && window.isSecureContext;
    try {
      const dataUrl = await toPng(el, { pixelRatio: 2, cacheBust: true });
      // Convert data URL locally to avoid CSP connect-src restrictions on `fetch(data:...)`.
      const blob = dataUrlToBlob(dataUrl);
      if (navigator.clipboard && "write" in navigator.clipboard) {
        try {
          await navigator.clipboard.write([new ClipboardItem({ "image/png": blob })]);
          setMsg(`${label} copied to clipboard`);
          return;
        } catch (clipErr) {
          if (!secure) {
            console.error(
              "[HideoutButler] PNG export: Pasting a PNG to the system clipboard is blocked on plain HTTP in most browsers. " +
                "Only https://, http://localhost, and http://127.0.0.1 are treated as “secure” for this API. " +
                "A PNG download is offered instead. Browser error —",
              errDetail(clipErr),
            );
            console.error("[HideoutButler] PNG export: original error object", clipErr);
          } else {
            console.error(
              "[HideoutButler] PNG export: Clipboard write failed; saving a PNG file instead. Reason —",
              errDetail(clipErr),
            );
            console.error("[HideoutButler] PNG export: original error object", clipErr);
          }
        }
      } else if (!secure) {
        console.error(
          "[HideoutButler] PNG export: navigator.clipboard is unavailable (typical on plain HTTP). A PNG will be downloaded instead of copied.",
        );
      }
      const a = document.createElement("a");
      a.href = dataUrl;
      a.download = `${baseName}.png`;
      a.click();
      setMsg("downloaded PNG");
    } catch (e) {
      setMsg("could not export image");
      console.error(
        "[HideoutButler] PNG export: Could not build or read the image (CORS, canvas taint, or other).",
        e instanceof Error ? e.message : e,
      );
      if (e instanceof Error && e.stack) {
        console.error("[HideoutButler] PNG export: stack", e.stack);
      }
    }
  };

  const runDownload = async (
    r: React.RefObject<HTMLDivElement | null>,
    fileSuffix: "compact" | "detail",
  ) => {
    const el = r.current;
    if (!el) {
      setMsg("nothing to capture");
      return;
    }
    setMsg("rendering…");
    try {
      const dataUrl = await toPng(el, { pixelRatio: 2, cacheBust: true });
      const a = document.createElement("a");
      a.href = dataUrl;
      a.download = `${baseName}-${fileSuffix}.png`;
      a.click();
      setMsg(`Downloaded ${fileSuffix} PNG`);
    } catch (e) {
      setMsg("could not export image");
      console.error(
        "[HideoutButler] PNG export: Could not build or read the image (CORS, canvas taint, or other).",
        e instanceof Error ? e.message : e,
      );
      if (e instanceof Error && e.stack) {
        console.error("[HideoutButler] PNG export: stack", e.stack);
      }
    }
  };

  const exportRowH = "h-9";
  const downloadIconPairedClass =
    `inline-flex ${exportRowH} w-9 shrink-0 items-center justify-center rounded-md rounded-l-none border border-ink-600 border-l-0 bg-ink-800 text-ember-300 hover:border-ember-400/40 hover:text-ember-200 focus-visible:outline focus-visible:outline-2 focus-visible:outline-ember-400/60`;

  return (
    <div className="shrink-0 space-y-1">
      <p className={PANE_SECTION_HEADING}>Image export (Discord)</p>
      <div className="flex w-full min-w-0 items-stretch gap-2">
        <div className="flex min-h-0 min-w-0 flex-1 items-stretch">
          <button
            type="button"
            className={`btn-ghost inline-flex min-w-0 flex-1 items-center justify-center gap-1 rounded-r-none px-2 text-xs sm:gap-1.5 ${exportRowH}`}
            onClick={() => void runCopy(compactRef, "Compact")}
            title="Copy PNG to clipboard (compact layout)"
            aria-label="Copy PNG to clipboard (compact layout)"
          >
            <IconImageExport />
            <span className="truncate">Image</span>
          </button>
          <button
            type="button"
            className={downloadIconPairedClass}
            onClick={() => void runDownload(compactRef, "compact")}
            title="Download PNG (compact)"
            aria-label="Download PNG (compact)"
          >
            {downloadIconSvg()}
          </button>
        </div>
        <div className="flex min-h-0 min-w-0 flex-1 items-stretch">
          <button
            type="button"
            className={`btn-ghost inline-flex min-w-0 flex-1 items-center justify-center gap-1 rounded-r-none px-2 text-xs sm:gap-1.5 ${exportRowH}`}
            onClick={() => void runCopy(detailRef, "Detail")}
            title="Copy PNG to clipboard (detail layout)"
            aria-label="Copy PNG to clipboard (detail layout)"
          >
            <IconImageExport />
            <span className="truncate">Image (detail)</span>
          </button>
          <button
            type="button"
            className={downloadIconPairedClass}
            onClick={() => void runDownload(detailRef, "detail")}
            title="Download PNG (detail)"
            aria-label="Download PNG (detail)"
          >
            {downloadIconSvg()}
          </button>
        </div>
      </div>
      {msg && <p className="text-[11px] text-ui-muted">{msg}</p>}
      <div className="pointer-events-none fixed -left-[10000px] top-0 z-0" aria-hidden>
        <div ref={compactRef}>
          <ItemExportSnapshot item={item} variant="compact" />
        </div>
        <div ref={detailRef} className="pt-1">
          <ItemExportSnapshot item={item} variant="detail" priceSnapshot={priceSnapshot} />
        </div>
      </div>
    </div>
  );
}
