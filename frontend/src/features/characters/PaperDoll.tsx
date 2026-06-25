import type { Item } from "@/api/types";
import { ItemCard } from "@/features/items/ItemCard";

type SlotDef = { id: string; label: string; gridArea: string; item?: Item };

const CORE_SLOTS: Omit<SlotDef, "item">[] = [
  { id: "Helm", label: "Helm", gridArea: "helm" },
  { id: "Amulet", label: "Amulet", gridArea: "amulet" },
  { id: "BodyArmour", label: "Body", gridArea: "body" },
  { id: "Gloves", label: "Gloves", gridArea: "gloves" },
  { id: "Ring", label: "Ring", gridArea: "ring" },
  { id: "Ring2", label: "Ring", gridArea: "ring2" },
  { id: "Belt", label: "Belt", gridArea: "belt" },
  { id: "Boots", label: "Boots", gridArea: "boots" },
];

function buildSlots(bySlot: Map<string, Item>): { slots: SlotDef[]; gridTemplateAreas: string } {
  const weaponMain = bySlot.get("Weapon");
  const weaponSwap = bySlot.get("Weapon2");
  const offMain = bySlot.get("Offhand");
  const offSwap = bySlot.get("Offhand2");

  const singleMainSide = Boolean(weaponMain) !== Boolean(weaponSwap);
  const singleOffSide = Boolean(offMain) !== Boolean(offSwap);

  const slots: SlotDef[] = [];

  if (singleMainSide) {
    slots.push({
      id: "Weapon",
      label: weaponMain ? "Main hand" : "Weapon swap",
      gridArea: "weapon",
      item: weaponMain ?? weaponSwap,
    });
  } else {
    slots.push(
      { id: "Weapon", label: "Main hand", gridArea: "weapon", item: weaponMain },
      { id: "Weapon2", label: "Weapon swap", gridArea: "weapon2", item: weaponSwap },
    );
  }

  for (const slot of CORE_SLOTS.slice(0, 2)) {
    slots.push({ ...slot, item: bySlot.get(slot.id) });
  }

  if (singleOffSide) {
    slots.push({
      id: "Offhand",
      label: offMain ? "Off hand" : "Off hand swap",
      gridArea: "offhand",
      item: offMain ?? offSwap,
    });
  } else {
    slots.push(
      { id: "Offhand", label: "Off hand", gridArea: "offhand", item: offMain },
      { id: "Offhand2", label: "Off hand swap", gridArea: "offhand2", item: offSwap },
    );
  }

  for (const slot of CORE_SLOTS.slice(2)) {
    slots.push({ ...slot, item: bySlot.get(slot.id) });
  }

  const gridTemplateAreas = singleMainSide
    ? `
          "weapon helm offhand"
          "weapon amulet offhand"
          "weapon body offhand2"
          "gloves body ring"
          "belt boots ring2"
        `
    : `
          "weapon helm offhand"
          "weapon2 helm offhand"
          "weapon amulet offhand2"
          "weapon2 body offhand2"
          "gloves body ring"
          "belt boots ring2"
        `;

  return { slots, gridTemplateAreas };
}

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

  const { slots, gridTemplateAreas } = buildSlots(bySlot);

  return (
    <div
      className="grid gap-3"
      style={{
        gridTemplateAreas,
        gridTemplateColumns: "1fr 1fr 1fr",
        gridAutoRows: "minmax(68px, auto)",
      }}
    >
      {slots.map(({ id, label, gridArea, item }) => (
        <div key={id} style={{ gridArea }} className="min-h-[68px]">
          {item ? (
            <ItemCard
              item={item}
              selected={selectedItemId === item.id}
              onClick={onSelectItem}
              className="h-full"
            />
          ) : (
            <div className="panel grid h-full min-h-[68px] place-items-center border border-dashed border-ink-700 text-xs text-ui-muted">
              {label}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
