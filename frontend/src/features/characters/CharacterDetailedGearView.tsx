import type { Item } from "@/api/types";
import { ItemExportSnapshot } from "@/features/items/ItemImageExport";

const GRID_TEMPLATE_AREAS = `
  "weapon helm offhand"
  "weapon amulet offhand"
  "weapon body offhand"
  "gloves body ring"
  "belt boots ring2"
`;

type CoreSlotDef = { id: string; label: string; gridArea: string };

const CORE_SLOTS: CoreSlotDef[] = [
  { id: "Helm", label: "Helm", gridArea: "helm" },
  { id: "Amulet", label: "Amulet", gridArea: "amulet" },
  { id: "BodyArmour", label: "Body", gridArea: "body" },
  { id: "Gloves", label: "Gloves", gridArea: "gloves" },
  { id: "Ring", label: "Ring", gridArea: "ring" },
  { id: "Ring2", label: "Ring", gridArea: "ring2" },
  { id: "Belt", label: "Belt", gridArea: "belt" },
  { id: "Boots", label: "Boots", gridArea: "boots" },
];

function EmptySlot({ label }: { label: string }) {
  return (
    <div className="grid min-h-[120px] place-items-center rounded-md border border-dashed border-ink-700 text-xs text-ui-muted">
      {label}
    </div>
  );
}

function DetailedSideColumn({
  gridArea,
  emptyLabel,
  mainItem,
  swapItem,
}: {
  gridArea: string;
  emptyLabel: string;
  mainItem?: Item;
  swapItem?: Item;
}) {
  const hasAny = Boolean(mainItem) || Boolean(swapItem);
  return (
    <div style={{ gridArea }} className="flex min-h-[120px] flex-col gap-2">
      {!hasAny ? (
        <EmptySlot label={emptyLabel} />
      ) : (
        <>
          {mainItem ? (
            <ItemExportSnapshot item={mainItem} variant="compact" />
          ) : (
            <EmptySlot label={emptyLabel} />
          )}
          {swapItem ? <ItemExportSnapshot item={swapItem} variant="compact" /> : null}
        </>
      )}
    </div>
  );
}

export interface CharacterDetailedGearViewProps {
  equipped: Item[];
  jewels?: Item[];
  gems?: Item[];
}

export function CharacterDetailedGearView({
  equipped,
  jewels = [],
  gems = [],
}: CharacterDetailedGearViewProps) {
  const bySlot = new Map<string, Item>();
  for (const item of equipped) {
    if (item.inventory_id) bySlot.set(item.inventory_id, item);
  }

  return (
    <div className="space-y-3">
      <div
        className="grid gap-2"
        style={{
          gridTemplateAreas: GRID_TEMPLATE_AREAS,
          gridTemplateColumns: "1fr 1fr 1fr",
          gridAutoRows: "minmax(120px, auto)",
        }}
        data-testid="character-detailed-gear"
      >
        <DetailedSideColumn
          gridArea="weapon"
          emptyLabel="Main hand"
          mainItem={bySlot.get("Weapon")}
          swapItem={bySlot.get("Weapon2")}
        />
        {CORE_SLOTS.slice(0, 2).map(({ id, label, gridArea }) => {
          const item = bySlot.get(id);
          return (
            <div key={id} style={{ gridArea }}>
              {item ? <ItemExportSnapshot item={item} variant="compact" /> : <EmptySlot label={label} />}
            </div>
          );
        })}
        <DetailedSideColumn
          gridArea="offhand"
          emptyLabel="Off hand"
          mainItem={bySlot.get("Offhand")}
          swapItem={bySlot.get("Offhand2")}
        />
        {CORE_SLOTS.slice(2).map(({ id, label, gridArea }) => {
          const item = bySlot.get(id);
          return (
            <div key={id} style={{ gridArea }}>
              {item ? <ItemExportSnapshot item={item} variant="compact" /> : <EmptySlot label={label} />}
            </div>
          );
        })}
      </div>
      {jewels.length > 0 && (
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
          {jewels.map((item) => (
            <ItemExportSnapshot key={item.id} item={item} variant="compact" />
          ))}
        </div>
      )}
      {gems.length > 0 && (
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
          {gems.map((item) => (
            <ItemExportSnapshot key={item.id} item={item} variant="compact" />
          ))}
        </div>
      )}
    </div>
  );
}
