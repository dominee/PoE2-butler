import type { Item } from "@/api/types";
import { ItemCard } from "@/features/items/ItemCard";

const SLOT_LAYOUT: { id: string; label: string; gridArea: string }[] = [
  { id: "Helm", label: "Helm", gridArea: "helm" },
  { id: "Amulet", label: "Amulet", gridArea: "amulet" },
  { id: "Weapon", label: "Main hand", gridArea: "weapon" },
  { id: "Weapon2", label: "Off hand", gridArea: "offhand" },
  { id: "Offhand", label: "Off hand", gridArea: "offhand" },
  { id: "Offhand2", label: "Off hand swap", gridArea: "offhand2" },
  { id: "BodyArmour", label: "Body", gridArea: "body" },
  { id: "Gloves", label: "Gloves", gridArea: "gloves" },
  { id: "Ring", label: "Ring", gridArea: "ring" },
  { id: "Ring2", label: "Ring", gridArea: "ring2" },
  { id: "Belt", label: "Belt", gridArea: "belt" },
  { id: "Boots", label: "Boots", gridArea: "boots" },
];

export interface PaperDollProps {
  equipped: Item[];
  selectedItemId?: string | null;
  onSelectItem?: (item: Item) => void;
}

export function PaperDoll({ equipped, selectedItemId, onSelectItem }: PaperDollProps) {
  const bySlot = new Map<string, Item>();
  for (const item of equipped) {
    if (item.inventory_id) bySlot.set(item.inventory_id, item);
  }

  return (
    <div
      className="grid gap-3"
      style={{
        gridTemplateAreas: `
          "weapon helm offhand"
          "weapon amulet offhand"
          "weapon body offhand2"
          "gloves body ring"
          "belt boots ring2"
        `,
        gridTemplateColumns: "1fr 1fr 1fr",
      }}
    >
      {SLOT_LAYOUT.map(({ id, label, gridArea }) => {
        const item = bySlot.get(id);
        return (
          <div key={id} style={{ gridArea }}>
            {item ? (
              <ItemCard
                item={item}
                selected={selectedItemId === item.id}
                onClick={onSelectItem}
              />
            ) : (
              <div className="panel grid h-full min-h-[68px] place-items-center border border-dashed border-ink-700 text-xs text-ink-500">
                {label}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
