/**
 * Table view for all character items (equipped gear + passive jewels).
 *
 * Mirrors the StashTable visual pattern but without virtualisation —
 * a character has at most ~20 items, so it's fine to render them all.
 */

import type { Item } from "@/api/types";
import { formatChaos } from "@/features/items/PriceBadge";
import { stripTags } from "@/utils/modText";

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
};

export interface CharacterTableProps {
  equipped: Item[];
  jewels: Item[];
  selectedItemId: string | null;
  onSelect: (item: Item) => void;
}

export function CharacterTable({
  equipped,
  jewels,
  selectedItemId,
  onSelect,
}: CharacterTableProps) {
  const allItems = [...equipped, ...jewels];

  if (allItems.length === 0) {
    return <p className="text-sm text-ink-500">No items equipped.</p>;
  }

  return (
    <div
      className="overflow-auto rounded-md border border-ink-700 bg-ink-950/70"
      role="grid"
      aria-label="Equipped items"
    >
      {/* Header */}
      <div
        className="grid grid-cols-[120px_minmax(140px,2fr)_minmax(110px,1fr)_60px_80px_1fr] gap-2 border-b border-ink-700 bg-ink-900/95 px-3 py-2 text-[11px] uppercase tracking-wide text-ink-400"
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
        const slot = item.inventory_id ? (SLOT_LABELS[item.inventory_id] ?? item.inventory_id) : "—";

        return (
          <button
            type="button"
            key={item.id}
            onClick={() => onSelect(item)}
            className={[
              "grid w-full grid-cols-[120px_minmax(140px,2fr)_minmax(110px,1fr)_60px_80px_1fr] items-center gap-2 px-3 py-2 text-left text-sm",
              "border-b border-ink-800 transition hover:bg-ink-800/70 focus:outline-none focus-visible:bg-ink-800",
              isSelected ? "bg-ember-500/10 text-ember-200" : "text-parchment-100",
            ].join(" ")}
            role="row"
            aria-selected={isSelected}
            data-testid="char-table-row"
          >
            <span className="truncate text-xs text-ink-400">{slot}</span>
            <span className="flex items-center gap-1.5 truncate">
              {item.icon && (
                <img
                  src={item.icon}
                  alt=""
                  className="h-5 w-5 shrink-0 object-contain"
                  loading="lazy"
                />
              )}
              <span className="truncate">{item.name || item.type_line || "—"}</span>
            </span>
            <span className="truncate text-parchment-100/70">{item.base_type}</span>
            <span className="text-ink-400">{item.ilvl ?? "—"}</span>
            <span className="text-xs text-parchment-100/80">—</span>
            <span className="truncate text-xs text-rarity-magic/90">
              {item.explicit_mods
                .slice(0, 2)
                .map((m) => stripTags(m))
                .join(" · ")}
            </span>
          </button>
        );
      })}
    </div>
  );
}
