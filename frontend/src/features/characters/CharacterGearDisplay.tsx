import type { CharacterDetail } from "@/api/types";
import {
  collectCharacterSkillGemsForDisplay,
  collectCharacterSupportGemsForDisplay,
} from "@/features/characters/characterGemFilter";
import { PaperDoll } from "@/features/characters/PaperDoll";
import { collectPaperDollItems } from "@/features/characters/paperDollItems";
import { ItemCard } from "@/features/items/ItemCard";
import { PANE_SECTION_HEADING } from "@/features/items/ItemModPresentation";

export interface CharacterGearDisplayProps {
  detail: CharacterDetail;
  selectedItemId?: string | null;
  onSelectItem?: (item: import("@/api/types").Item) => void;
  readOnly?: boolean;
}

export function CharacterGearDisplay({
  detail,
  selectedItemId,
  onSelectItem,
  readOnly = false,
}: CharacterGearDisplayProps) {
  const click = readOnly ? undefined : onSelectItem;
  const skillGems = collectCharacterSkillGemsForDisplay(detail);
  const supportGems = collectCharacterSupportGemsForDisplay(detail);

  return (
    <>
      <PaperDoll
        equipped={collectPaperDollItems(detail)}
        selectedItemId={selectedItemId}
        onSelectItem={click}
      />
      {detail.jewels?.length > 0 && (
        <div className="mt-2">
          <h3 className={`mb-1 ${PANE_SECTION_HEADING}`}>Jewels</h3>
          <div className="grid grid-cols-2 gap-1.5">
            {detail.jewels.map((jewel) => (
              <ItemCard
                key={jewel.id}
                item={jewel}
                selected={selectedItemId === jewel.id}
                onClick={click}
              />
            ))}
          </div>
        </div>
      )}
      {skillGems.length > 0 && (
        <div className="mt-2">
          <h3 className={`mb-1 ${PANE_SECTION_HEADING}`}>Skill gems</h3>
          <div className="grid grid-cols-2 gap-1.5">
            {skillGems.map((gem) => (
              <ItemCard
                key={gem.id}
                item={gem}
                selected={selectedItemId === gem.id}
                onClick={click}
              />
            ))}
          </div>
        </div>
      )}
      {supportGems.length > 0 && (
        <div className="mt-2">
          <h3 className={`mb-1 ${PANE_SECTION_HEADING}`}>Support gems</h3>
          <div className="grid grid-cols-2 gap-1.5">
            {supportGems.map((gem) => (
              <ItemCard
                key={gem.id}
                item={gem}
                selected={selectedItemId === gem.id}
                onClick={click}
              />
            ))}
          </div>
        </div>
      )}
    </>
  );
}
