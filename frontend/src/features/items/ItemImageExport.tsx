import { useRef, useState } from "react";
import { toPng } from "html-to-image";
import type { Item, ItemRarity } from "@/api/types";
import { itemIconForCanvasProxy } from "@/utils/poecdnIcon";
import { stripTags } from "@/utils/modText";

const LOG_PREFIX = "[HideoutButler] PNG export";

function errDetail(err: unknown): string {
  if (err instanceof Error) return err.message;
  return String(err);
}

const RARITY_BORDER: Record<ItemRarity, string> = {
  Normal: "border-ink-600",
  Magic: "border-rarity-magic/60",
  Rare: "border-rarity-rare/60",
  Unique: "border-rarity-unique/60",
  Currency: "border-rarity-currency/60",
  Gem: "border-rarity-gem/60",
  DivinationCard: "border-ink-600",
  QuestItem: "border-ink-600",
};

function ItemExportCard({
  item,
  detail,
}: {
  item: Item;
  detail: boolean;
}) {
  const b = RARITY_BORDER[item.rarity] ?? "border-ink-600";
  const iconSrc = itemIconForCanvasProxy(item.icon) ?? item.icon;
  return (
    <div
      className={`${b} w-[360px] rounded-md border-2 bg-ink-900 p-3 text-left text-sm text-parchment-100 shadow-lg`}
    >
      <div className="font-display text-sm font-semibold text-ember-200/90">PoE2 Hideout Butler</div>
      {item.icon && (
        <div className="mt-2 flex items-start gap-2">
          <img
            src={iconSrc}
            alt=""
            className="h-12 w-12 object-contain"
          />
          <div className="min-w-0">
            {item.name && <div className="break-words text-base">{item.name}</div>}
            <div className="text-parchment-100/80">{item.type_line}</div>
            <div className="text-[10px] uppercase text-ink-500">
              {item.rarity} {item.ilvl != null ? `· ilvl ${item.ilvl}` : ""}
            </div>
          </div>
        </div>
      )}
      {!item.icon && (
        <div className="mt-2">
          {item.name && <div className="font-semibold">{item.name}</div>}
          <div className="text-parchment-100/80">{item.type_line}</div>
        </div>
      )}
      {detail && item.explicit_mods.length > 0 && (
        <ul className="mt-2 list-none space-y-0.5 text-[12px] text-rarity-magic/90">
          {item.explicit_mods.map((m, i) => (
            <li key={i} className="break-words">
              {stripTags(m)}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function ItemImageExportActions({ item }: { item: Item }) {
  const compactRef = useRef<HTMLDivElement>(null);
  const detailRef = useRef<HTMLDivElement>(null);
  const [msg, setMsg] = useState<string | null>(null);

  const run = async (r: React.RefObject<HTMLDivElement | null>, label: string) => {
    const el = r.current;
    if (!el) {
      setMsg("nothing to capture");
      return;
    }
    setMsg("rendering…");
    const secure = typeof window !== "undefined" && window.isSecureContext;
    try {
      const dataUrl = await toPng(el, { pixelRatio: 2, cacheBust: true });
      const res = await fetch(dataUrl);
      const blob = await res.blob();
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
      a.download = `item-${item.id?.slice(0, 8) ?? "item"}.png`;
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

  return (
    <div className="shrink-0 space-y-1">
      <p className="text-[10px] uppercase tracking-widest text-ink-500">Image export (Discord)</p>
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          className="btn-ghost text-xs"
          onClick={() => void run(compactRef, "Compact")}
        >
          Copy PNG (compact)
        </button>
        <button
          type="button"
          className="btn-ghost text-xs"
          onClick={() => void run(detailRef, "Detail")}
        >
          Copy PNG (detail)
        </button>
      </div>
      {msg && <p className="text-[11px] text-ink-500">{msg}</p>}
      <div className="pointer-events-none fixed -left-[10000px] top-0 z-0" aria-hidden>
        <div ref={compactRef}>
          <ItemExportCard item={item} detail={false} />
        </div>
        <div ref={detailRef} className="pt-1">
          <ItemExportCard item={item} detail={true} />
        </div>
      </div>
    </div>
  );
}
