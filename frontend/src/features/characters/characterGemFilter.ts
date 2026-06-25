import type { Item } from "@/api/types";
import { stripTags } from "@/utils/modText";

/** Tiered generic supports: "Brutality I", "Overabundance II", etc. */
const TIERED_SUPPORT_RE = /\s+(I{1,3}|IV|V|VI{0,3}|IX|X)$/;

function propertyText(item: Item): string {
  return item.properties.map((p) => stripTags(p.name)).join(" ").toLowerCase();
}

function isLineageSupport(item: Item): boolean {
  return propertyText(item).includes("lineage");
}

function isGenericSupport(item: Item): boolean {
  const props = propertyText(item);
  if (props.includes("lineage")) return false;
  return props.includes("support");
}

function isTieredGenericSupport(item: Item): boolean {
  return TIERED_SUPPORT_RE.test(item.type_line.trim());
}

/**
 * Character gem panel: show active skills, ascendancy gems, and special supports
 * (Lineage, etc.) — hide common tiered supports socketed in skill links.
 */
export function isNotableCharacterGem(item: Item): boolean {
  if (item.inventory_id === "AscendancySkills" || item.inventory_id === "DefaultAttackSkills") {
    return true;
  }
  if (isLineageSupport(item)) return true;
  if (isTieredGenericSupport(item)) return false;
  if (isGenericSupport(item)) return false;
  return item.rarity === "Gem";
}

export function filterNotableCharacterGems(gems: Item[]): Item[] {
  return gems.filter(isNotableCharacterGem);
}
