/**
 * Table view for all character items (equipped gear + passive jewels).
 *
 * Mirrors the StashTable visual pattern but without virtualisation —
 * a character has at most ~20 items, so it's fine to render them all.
 */

import type { Item, PriceEstimate } from "@/api/types";
import { itemIconDisplayUrl } from "@/features/items/itemRarityFavicon";
import {
  formatChaos,
  formatChaosAsDivExLine,
  type CurrencyChaosPair,
} from "@/features/items/itemMetrics";
import { ModText } from "@/features/items/ItemModPresentation";
import {
  isCharacterSkillGem,
  isLineageSupportGem,
} from "@/features/characters/characterGemFilter";

const SLOT_LABELS: Record<string, string> = {
  Helm: "Helm",
  Amulet: "Amulet",
  Weapon: "Main hand",
  Weapon2: "Weapon swap",
  Offhand: "Off hand",
  Offhand2: "Off hand swap",
  BodyArmour: "Body armour",
  Gloves: "Gloves",
  Ring: "Ring (L)",
  Ring2: "Ring (R)",
  Belt: "Belt",
  Boots: "Boots",
  PassiveJewels: "Jewel",
  SkillSlots: "Skill gem",
  AscendancySkills: "Ascendancy skill",
};

export interface CharacterTableProps {
  equipped: Item[];
  gems: Item[];
  supportGems?: Item[];
  jewels: Item[];
  other: Item[];
  selectedItemId: string | null;
  onSelect: (item: Item) => void;
  prices?: Record<string, PriceEstimate | null>;
  valuableThreshold?: number;
  currencyChaos?: CurrencyChaosPair | null;
}

function slotLabel(item: Item): string {
  if (item.inventory_id) {
    return SLOT_LABELS[item.inventory_id] ?? item.inventory_id;
  }
  if (isCharacterSkillGem(item)) return "Skill gem";
  if (isLineageSupportGem(item)) return "Support gem";
  return "—";
}

function formatItemPrice(
  price: PriceEstimate | null | undefined,
  currencyChaos: CurrencyChaosPair | null | undefined,
): string {
  if (!price) return "—";
  if (currencyChaos) {
    return formatChaosAsDivExLine(price.chaos_equiv, currencyChaos);
  }
  return `${formatChaos(price.chaos_equiv)}c`;
}

export function CharacterTable({
  equipped,
  gems,
  supportGems = [],
  jewels,
  other,
  selectedItemId,
  onSelect,
  prices,
  valuableThreshold,
  currencyChaos,
}: CharacterTableProps) {
  const allItems = [...equipped, ...gems, ...supportGems, ...jewels, ...other];

  if (allItems.length === 0) {
    return <p className="text-sm text-ui-muted">No items equipped.</p>;
  }

  return (
    <div
      className="overflow-auto rounded-md border border-ink-700 bg-ink-950/70"
      role="grid"
      aria-label="Equipped items"
    >
      {/* Header */}
      <div
        className="grid grid-cols-[120px_minmax(140px,2fr)_minmax(110px,1fr)_60px_minmax(80px,1fr)_1fr] gap-2 border-b border-ink-700 bg-ink-900/95 px-3 py-2 text-[11px] uppercase tracking-wide text-ui-muted"
        role="row"
      >
        <span>Slot</span>
        <span>Name</span>
        <span>Base type</span>
        <span>iLvl</span>
        <span>Price</span>
        <span>Mods</span>
      </div>

      {/* Rows */}
      {allItems.map((item) => {
        const isSelected = item.id === selectedItemId;
        const slot = slotLabel(item);
        const price = prices?.[item.id];
        const valuable =
          price && valuableThreshold != null && price.chaos_equiv >= valuableThreshold;

        return (
          <button
            type="button"
            key={item.id}
            onClick={() => onSelect(item)}
            className={[
              "grid w-full grid-cols-[120px_minmax(140px,2fr)_minmax(110px,1fr)_60px_minmax(80px,1fr)_1fr] items-center gap-2 px-3 py-2 text-left text-sm",
              "border-b border-ink-800 transition hover:bg-ink-800/70 focus:outline-none focus-visible:bg-ink-800 focus-visible:ring-2 focus-visible:ring-ember-400/70 focus-visible:ring-inset",
              isSelected ? "bg-ember-500/10 text-ember-200" : "text-parchment-100",
            ].join(" ")}
            role="row"
            aria-selected={isSelected}
            data-testid="char-table-row"
          >
            <span className="truncate text-xs text-ui-muted">{slot}</span>
            <span className="flex items-center gap-1.5 truncate">
              <img
                src={itemIconDisplayUrl(item)}
                alt=""
                className="h-5 w-5 shrink-0 object-contain"
                loading="lazy"
              />
              <span className="truncate">{item.name || item.type_line || "—"}</span>
            </span>
            <span className="truncate text-parchment-100/70">{item.base_type}</span>
            <span className="text-ui-muted">{item.ilvl ?? "—"}</span>
            <span
              className={
                valuable
                  ? "truncate text-xs font-semibold text-yellow-300"
                  : "truncate text-xs text-parchment-100/90"
              }
            >
              {formatItemPrice(price, currencyChaos)}
            </span>
            <span className="truncate text-xs text-rarity-magic/90">
              {item.explicit_mods.slice(0, 2).map((m, i) => (
                <span key={i}>
                  {i > 0 ? " · " : null}
                  <ModText raw={m} />
                </span>
              ))}
            </span>
          </button>
        );
      })}
    </div>
  );
}
