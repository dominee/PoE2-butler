import type { CharacterDetail } from "@/api/types";
import {
  collectCharacterSkillGemsForDisplay,
  collectCharacterSupportGemsForDisplay,
  gemSourceLabel,
} from "@/features/characters/characterGemFilter";
import { PaperDoll } from "@/features/characters/PaperDoll";
import { collectPaperDollItems, collectCharmItems } from "@/features/characters/paperDollItems";
import { ItemCard } from "@/features/items/ItemCard";
import { PANE_SECTION_HEADING } from "@/features/items/ItemModPresentation";

/** Small inline SVG icons for gem source indicators. */
function SourceIcon({ source }: { source: string }) {
  if (source === "From Weapon")
    return (
      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" className="inline h-3 w-3 shrink-0" fill="currentColor" aria-hidden="true">
        <path d="M11.5 0L16 4.5l-1 1-1-1-7 7 .5.5-1.5 2.5L4 16l-1.5-1.5 1-2.5.5-.5-1-1 .5-.5 1 1 7-7-1-1zM2 12l1 1-.5 1.5L1 16l-.5-1.5L0 13l1.5-.5z"/>
      </svg>
    );
  if (source === "From Skill Tree")
    return (
      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" className="inline h-3 w-3 shrink-0" fill="currentColor" aria-hidden="true">
        <circle cx="8" cy="8" r="2.5"/>
        <path d="M8 0v3M8 13v3M0 8h3M13 8h3M2.3 2.3l2.1 2.1M11.6 11.6l2.1 2.1M13.7 2.3l-2.1 2.1M4.4 11.6l-2.1 2.1"/>
        <circle cx="8" cy="8" r="5.5" fill="none" stroke="currentColor" strokeWidth="1"/>
      </svg>
    );
  if (source === "Ascendancy")
    return (
      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" className="inline h-3 w-3 shrink-0" fill="currentColor" aria-hidden="true">
        <path d="M8 0l1.5 5h5.5l-4.5 3.3 1.7 5.2L8 10.5l-4.2 3 1.7-5.2L1 5h5.5z"/>
      </svg>
    );
  return null;
}

/** One-line annotation shown below a skill gem card (source + label). */
export function GemSourceAnnotation({ source }: { source: string }) {
  return (
    <p className="mt-0.5 flex items-center gap-1 text-[10px] italic text-ui-muted">
      <SourceIcon source={source} />
      {source}
    </p>
  );
}

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
        charms={collectCharmItems(detail)}
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
                sourceLabel={gemSourceLabel(gem)}
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
