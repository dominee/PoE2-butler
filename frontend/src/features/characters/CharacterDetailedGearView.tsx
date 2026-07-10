import type { Item } from "@/api/types";
import { ItemExportSnapshot } from "@/features/items/ItemImageExport";
import { PANE_SECTION_HEADING } from "@/features/items/ItemModPresentation";

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

const ITEM_CARD = {
  showBranding: false,
  embedded: true,
} as const;

function EmptySlot({ label }: { label: string }) {
  return (
    <div className="grid min-h-[72px] place-items-center rounded-md border border-dashed border-ink-700 text-[10px] text-ui-muted">
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
    <div style={{ gridArea }} className="flex min-h-0 min-w-0 flex-col gap-1.5">
      {!hasAny ? (
        <EmptySlot label={emptyLabel} />
      ) : (
        <>
          {mainItem ? (
            <ItemExportSnapshot item={mainItem} variant="compact" {...ITEM_CARD} />
          ) : (
            <EmptySlot label={emptyLabel} />
          )}
          {swapItem ? (
            <ItemExportSnapshot item={swapItem} variant="compact" {...ITEM_CARD} />
          ) : null}
        </>
      )}
    </div>
  );
}

export interface CharacterDetailedGearViewProps {
  equipped: Item[];
  jewels?: Item[];
  gems?: Item[];
  supportGems?: Item[];
  /** ``doll`` = paper-doll slots (web). ``grid`` = compact multi-column (PNG export). */
  layout?: "doll" | "grid";
}

export function CharacterDetailedGearView({
  equipped,
  jewels = [],
  gems = [],
  supportGems = [],
  layout = "doll",
}: CharacterDetailedGearViewProps) {
  const bySlot = new Map<string, Item>();
  for (const item of equipped) {
    if (item.inventory_id) bySlot.set(item.inventory_id, item);
  }

  const allItems = [...equipped, ...jewels, ...gems, ...supportGems];

  if (layout === "grid") {
    return (
      <div className="space-y-2" data-testid="character-detailed-gear">
        <div className="grid grid-cols-3 gap-2 xl:grid-cols-4">
          {allItems.map((item) => (
            <ItemExportSnapshot key={item.id} item={item} variant="compact" {...ITEM_CARD} />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-3" data-testid="character-detailed-gear">
      <div
        className="grid min-w-0 gap-1.5"
        style={{
          gridTemplateAreas: GRID_TEMPLATE_AREAS,
          gridTemplateColumns: "minmax(0, 1fr) minmax(0, 1fr) minmax(0, 1fr)",
          gridAutoRows: "minmax(72px, auto)",
        }}
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
            <div key={id} style={{ gridArea }} className="min-w-0">
              {item ? (
                <ItemExportSnapshot item={item} variant="compact" {...ITEM_CARD} />
              ) : (
                <EmptySlot label={label} />
              )}
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
            <div key={id} style={{ gridArea }} className="min-w-0">
              {item ? (
                <ItemExportSnapshot item={item} variant="compact" {...ITEM_CARD} />
              ) : (
                <EmptySlot label={label} />
              )}
            </div>
          );
        })}
      </div>
      {jewels.length > 0 && (
        <div>
          <h3 className={`mb-1 ${PANE_SECTION_HEADING}`}>Jewels</h3>
          <div className="grid grid-cols-2 gap-1.5 lg:grid-cols-3">
            {jewels.map((item) => (
              <ItemExportSnapshot key={item.id} item={item} variant="compact" {...ITEM_CARD} />
            ))}
          </div>
        </div>
      )}
      {gems.length > 0 && (
        <div>
          <h3 className={`mb-1 ${PANE_SECTION_HEADING}`}>Skill gems</h3>
          <div className="grid grid-cols-2 gap-1.5 lg:grid-cols-3">
            {gems.map((item) => (
              <ItemExportSnapshot key={item.id} item={item} variant="compact" {...ITEM_CARD} />
            ))}
          </div>
        </div>
      )}
      {supportGems.length > 0 && (
        <div>
          <h3 className={`mb-1 ${PANE_SECTION_HEADING}`}>Support gems</h3>
          <div className="grid grid-cols-2 gap-1.5 lg:grid-cols-3">
            {supportGems.map((item) => (
              <ItemExportSnapshot key={item.id} item={item} variant="compact" {...ITEM_CARD} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

/** Paper doll + optional side columns for compact PNG/simple export. */
export function CharacterSimpleExportBody({
  equipped,
  jewels = [],
  gems = [],
  supportGems = [],
}: {
  equipped: Item[];
  jewels?: Item[];
  gems?: Item[];
  supportGems?: Item[];
}) {
  const sideItems = [...jewels, ...gems, ...supportGems];
  return (
    <div className="grid grid-cols-[minmax(320px,1fr)_minmax(0,1fr)] items-start gap-4">
      <CharacterDetailedGearView equipped={equipped} layout="doll" />
      {sideItems.length > 0 && (
        <div className="grid min-w-0 grid-cols-2 gap-1.5 content-start">
          {sideItems.map((item) => (
            <ItemExportSnapshot key={item.id} item={item} variant="compact" {...ITEM_CARD} />
          ))}
        </div>
      )}
    </div>
  );
}
