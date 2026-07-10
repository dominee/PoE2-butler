import type { Item, PriceEstimate } from "@/api/types";
import { ItemCard } from "@/features/items/ItemCard";
import type { CurrencyChaosPair } from "@/features/items/itemMetrics";

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
    <div className="panel grid h-full min-h-[68px] place-items-center border border-dashed border-ink-700 text-xs text-ui-muted">
      {label}
    </div>
  );
}

function SideColumn({
  gridArea,
  emptyLabel,
  mainItem,
  swapItem,
  selectedItemId,
  onSelectItem,
  prices,
  valuableThreshold,
  currencyChaos,
}: {
  gridArea: string;
  emptyLabel: string;
  mainItem?: Item;
  swapItem?: Item;
  selectedItemId?: string | null;
  onSelectItem?: (item: Item) => void;
  prices?: Record<string, PriceEstimate | null>;
  valuableThreshold?: number;
  currencyChaos?: CurrencyChaosPair | null;
}) {
  const hasAny = Boolean(mainItem) || Boolean(swapItem);

  return (
    <div style={{ gridArea }} className="flex min-h-[68px] flex-col gap-3">
      {!hasAny ? (
        <EmptySlot label={emptyLabel} />
      ) : (
        <>
          {mainItem ? (
            <ItemCard
              item={mainItem}
              selected={selectedItemId === mainItem.id}
              onClick={onSelectItem}
              className="min-h-[68px]"
              price={prices ? (prices[mainItem.id] ?? null) : undefined}
              valuableThreshold={valuableThreshold}
              currencyChaos={currencyChaos}
            />
          ) : (
            <EmptySlot label={emptyLabel} />
          )}
          {swapItem ? (
            <ItemCard
              item={swapItem}
              selected={selectedItemId === swapItem.id}
              onClick={onSelectItem}
              className="min-h-[68px]"
              price={prices ? (prices[swapItem.id] ?? null) : undefined}
              valuableThreshold={valuableThreshold}
              currencyChaos={currencyChaos}
            />
          ) : null}
        </>
      )}
    </div>
  );
}

export interface PaperDollProps {
  equipped: Item[];
  selectedItemId?: string | null;
  onSelectItem?: (item: Item) => void;
  prices?: Record<string, PriceEstimate | null>;
  valuableThreshold?: number;
  currencyChaos?: CurrencyChaosPair | null;
}

export function PaperDoll({
  equipped,
  selectedItemId,
  onSelectItem,
  prices,
  valuableThreshold,
  currencyChaos,
}: PaperDollProps) {
  const bySlot = new Map<string, Item>();
  for (const item of equipped) {
    if (item.inventory_id) bySlot.set(item.inventory_id, item);
  }

  const weaponMain = bySlot.get("Weapon");
  const weaponSwap = bySlot.get("Weapon2");
  const offMain = bySlot.get("Offhand");
  const offSwap = bySlot.get("Offhand2");

  return (
    <div
      className="grid gap-3"
      style={{
        gridTemplateAreas: GRID_TEMPLATE_AREAS,
        gridTemplateColumns: "1fr 1fr 1fr",
        gridAutoRows: "minmax(68px, auto)",
      }}
    >
      <SideColumn
        gridArea="weapon"
        emptyLabel="Main hand"
        mainItem={weaponMain}
        swapItem={weaponSwap}
        selectedItemId={selectedItemId}
        onSelectItem={onSelectItem}
        prices={prices}
        valuableThreshold={valuableThreshold}
        currencyChaos={currencyChaos}
      />

      {CORE_SLOTS.slice(0, 2).map(({ id, label, gridArea }) => {
        const item = bySlot.get(id);
        return (
          <div key={id} style={{ gridArea }} className="min-h-[68px]">
            {item ? (
              <ItemCard
                item={item}
                selected={selectedItemId === item.id}
                onClick={onSelectItem}
                className="h-full"
                price={prices ? (prices[item.id] ?? null) : undefined}
                valuableThreshold={valuableThreshold}
                currencyChaos={currencyChaos}
              />
            ) : (
              <EmptySlot label={label} />
            )}
          </div>
        );
      })}

      <SideColumn
        gridArea="offhand"
        emptyLabel="Off hand"
        mainItem={offMain}
        swapItem={offSwap}
        selectedItemId={selectedItemId}
        onSelectItem={onSelectItem}
        prices={prices}
        valuableThreshold={valuableThreshold}
        currencyChaos={currencyChaos}
      />

      {CORE_SLOTS.slice(2).map(({ id, label, gridArea }) => {
        const item = bySlot.get(id);
        return (
          <div key={id} style={{ gridArea }} className="min-h-[68px]">
            {item ? (
              <ItemCard
                item={item}
                selected={selectedItemId === item.id}
                onClick={onSelectItem}
                className="h-full"
                price={prices ? (prices[item.id] ?? null) : undefined}
                valuableThreshold={valuableThreshold}
                currencyChaos={currencyChaos}
              />
            ) : (
              <EmptySlot label={label} />
            )}
          </div>
        );
      })}
    </div>
  );
}
