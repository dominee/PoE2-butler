import { useRef, useState } from "react";
import { toPng } from "html-to-image";
import type { Item, ItemRarity } from "@/api/types";
import { itemIconForCanvasProxy } from "@/utils/poecdnIcon";

import { splitExplicitMods, usefulProperties } from "./itemPaneModel";
import { RARITY_NAME_CLASS } from "./itemVisualStyles";
import { computeItemScore } from "./itemMetrics";
import { itemRollScoreState } from "./modRollMetrics";
import { ExplicitModLine, ModDivider, ModSection, ModText } from "./ItemModPresentation";
import { PercentBar } from "./PercentBar";
import { itemReferenceHasAggregate, itemReferenceRollPcts, uniqueTypeRollPercent } from "./uniqueReferenceRoll";

const LOG_PREFIX = "[HideoutButler] PNG export";

function errDetail(err: unknown): string {
  if (err instanceof Error) return err.message;
  return String(err);
}

function dataUrlToBlob(dataUrl: string): Blob {
  const match = dataUrl.match(/^data:([^;,]+)?(;base64)?,(.*)$/);
  if (!match) {
    throw new Error("Invalid PNG data URL");
  }
  const mime = match[1] ?? "application/octet-stream";
  const isBase64 = Boolean(match[2]);
  const payload = match[3] ?? "";
  if (isBase64) {
    const binary = atob(payload);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i += 1) {
      bytes[i] = binary.charCodeAt(i);
    }
    return new Blob([bytes], { type: mime });
  }
  return new Blob([decodeURIComponent(payload)], { type: mime });
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
 * socketed items; room for more summary blocks later.
 */
function ItemExportSnapshot({ item, variant }: { item: Item; variant: "compact" | "detail" }) {
  const b = RARITY_CARD_BORDER[item.rarity] ?? "border-ink-600";
  const resolvedIcon = item.icon
    ? (itemIconForCanvasProxy(item.icon) ?? item.icon)
    : null;
  const nameClass = RARITY_NAME_CLASS[item.rarity as ItemRarity] ?? "";

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
      className={`${b} w-[400px] rounded-md border-2 bg-ink-900 p-3 text-left text-sm text-parchment-100 shadow-lg`}
    >
      <div className="font-display text-sm font-semibold text-ember-200/90">PoE2 Hideout Butler</div>
      {resolvedIcon && (
        <div className="mt-2 flex items-start gap-2">
          <div className="flex shrink-0 items-center justify-center rounded border border-ink-700 bg-ink-950/60 p-1">
            <img
              src={resolvedIcon}
              alt=""
              className="object-contain"
              style={{ width: item.w * 32, height: item.h * 32, maxWidth: 96, maxHeight: 96 }}
            />
          </div>
          <div className="min-w-0">
            {item.name && (
              <div className={`break-words text-base font-display ${nameClass}`}>{item.name}</div>
            )}
            <div className="text-parchment-100/80">{item.type_line}</div>
            <div className="mt-1 text-[10px] uppercase text-ink-500">
              <span>{item.rarity}</span>
              {item.ilvl != null && <span className="ml-1">ilvl {item.ilvl}</span>}
              {item.corrupted && <span className="ml-1 text-red-400">corrupted</span>}
            </div>
          </div>
        </div>
      )}
      {!item.icon && (
        <div className="mt-2">
          {item.name && <div className={`font-display text-base font-semibold ${nameClass}`}>{item.name}</div>}
          <div className="text-parchment-100/80">{item.type_line}</div>
        </div>
      )}

      {hasRollData && itemScore != null && (
        <div className="mt-2 flex items-center gap-2 text-xs">
          <span className="shrink-0 text-[10px] uppercase tracking-widest text-ink-500">
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
          <h4 className="text-[10px] font-semibold uppercase tracking-widest text-ink-500">Stats</h4>
          <ul className="mt-1 space-y-0.5 text-sm text-parchment-100/90">
            {visibleProps.map((p, idx) => (
               
              <li key={idx} className="flex justify-between gap-2">
                <span className="text-ink-500">{p.name}</span>
                <span className="text-right font-semibold text-parchment-50">
                  {p.value != null ? <ModText raw={p.value} /> : null}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {visibleReqs.length > 0 && (
        <div className="mt-1 text-xs text-ink-500">
          Requires {visibleReqs.map((r) => `${r.value} ${r.name}`).join(", ")}
        </div>
      )}

      {item.sockets.length > 0 && (
        <div className="mt-1 flex items-center gap-1.5">
          <span className="text-[10px] uppercase tracking-widest text-ink-500">Sockets</span>
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
            <h4 className="text-[10px] font-semibold uppercase tracking-widest text-ink-500">Implicit</h4>
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
          <h4 className="text-[10px] font-semibold uppercase tracking-widest text-ink-500">Runes &amp; Cores</h4>
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

      {item.explicit_mods.length > 0 && (
        <div className="mt-2 space-y-1">
          {showPrefixSuffix ? (
            <>
              {prefixes.length > 0 && (
                <div>
                  <h4 className="text-[10px] font-semibold uppercase tracking-widest text-ink-500">Prefixes</h4>
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
                  <h4 className="text-[10px] font-semibold uppercase tracking-widest text-ink-500">Suffixes</h4>
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
      {/* detail variant: reserve space for price, roll tables, etc. in future — Runes & Cores above */}
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

export function ItemImageExportActions({ item }: { item: Item }) {
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
              `${LOG_PREFIX}: Pasting a PNG to the system clipboard is blocked on plain HTTP in most browsers. ` +
                "Only https://, http://localhost, and http://127.0.0.1 are treated as “secure” for this API. " +
                "A PNG download is offered instead. Browser error —",
              errDetail(clipErr),
            );
            console.error(`${LOG_PREFIX}: original error object`, clipErr);
          } else {
            console.error(
              `${LOG_PREFIX}: Clipboard write failed; saving a PNG file instead. Reason —`,
              errDetail(clipErr),
            );
            console.error(`${LOG_PREFIX}: original error object`, clipErr);
          }
        }
      } else if (!secure) {
        console.error(
          `${LOG_PREFIX}: navigator.clipboard is unavailable (typical on plain HTTP). A PNG will be downloaded instead of copied.`,
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
        `${LOG_PREFIX}: Could not build or read the image (CORS, canvas taint, or other).`,
        e instanceof Error ? e.message : e,
      );
      if (e instanceof Error && e.stack) {
        console.error(`${LOG_PREFIX}: stack`, e.stack);
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
        `${LOG_PREFIX}: Could not build or read the image (CORS, canvas taint, or other).`,
        e instanceof Error ? e.message : e,
      );
      if (e instanceof Error && e.stack) {
        console.error(`${LOG_PREFIX}: stack`, e.stack);
      }
    }
  };

  return (
    <div className="shrink-0 space-y-1">
      <p className="text-[10px] uppercase tracking-widest text-ink-500">Image export (Discord)</p>
      <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap">
        <div className="inline-flex items-stretch gap-0.5">
          <button
            type="button"
            className="btn-ghost rounded-r-none pr-2 text-xs sm:pr-2.5"
            onClick={() => void runCopy(compactRef, "Compact")}
          >
            Copy PNG (compact)
          </button>
          <button
            type="button"
            className="inline-flex w-7 shrink-0 items-center justify-center rounded-md rounded-l-none border border-ink-600 border-l-0 bg-ink-800 text-ember-300 hover:border-ember-400/40 hover:text-ember-200 focus-visible:outline focus-visible:outline-2 focus-visible:outline-ember-400/60"
            onClick={() => void runDownload(compactRef, "compact")}
            title="Download PNG (compact)"
            aria-label="Download PNG (compact)"
          >
            {downloadIconSvg()}
          </button>
        </div>
        <div className="inline-flex items-stretch gap-0.5">
          <button
            type="button"
            className="btn-ghost rounded-r-none pr-2 text-xs sm:pr-2.5"
            onClick={() => void runCopy(detailRef, "Detail")}
          >
            Copy PNG (detail)
          </button>
          <button
            type="button"
            className="inline-flex w-7 shrink-0 items-center justify-center rounded-md rounded-l-none border border-ink-600 border-l-0 bg-ink-800 text-ember-300 hover:border-ember-400/40 hover:text-ember-200 focus-visible:outline focus-visible:outline-2 focus-visible:outline-ember-400/60"
            onClick={() => void runDownload(detailRef, "detail")}
            title="Download PNG (detail)"
            aria-label="Download PNG (detail)"
          >
            {downloadIconSvg()}
          </button>
        </div>
      </div>
      {msg && <p className="text-[11px] text-ink-500">{msg}</p>}
      <div className="pointer-events-none fixed -left-[10000px] top-0 z-0" aria-hidden>
        <div ref={compactRef}>
          <ItemExportSnapshot item={item} variant="compact" />
        </div>
        <div ref={detailRef} className="pt-1">
          <ItemExportSnapshot item={item} variant="detail" />
        </div>
      </div>
    </div>
  );
}
