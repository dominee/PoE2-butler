import type { CharacterDetail, Item } from "@/api/types";
import { stripTags } from "@/utils/modText";

/** Tiered generic supports: "Brutality I", "Overabundance II", etc. */
const TIERED_SUPPORT_RE = /\s+(I{1,3}|IV|V|VI{0,3}|IX|X)$/;

function propertyText(item: Item): string {
  return item.properties.map((p) => stripTags(p.name)).join(" ").toLowerCase();
}

/** Lineage support gems (e.g. Rakiata's Flow) — priced and shown in Support gems. */
export function isLineageSupportGem(item: Item): boolean {
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

function isHiddenSocketSupport(item: Item): boolean {
  return item.rarity === "Gem" && (isGenericSupport(item) || isTieredGenericSupport(item));
}

/** Active skill gems (including ascendancy and item-granted), not supports. */
export function isCharacterSkillGem(item: Item): boolean {
  if (item.inventory_id === "AscendancySkills" || item.inventory_id === "DefaultAttackSkills") {
    return true;
  }
  if (isLineageSupportGem(item)) return false;
  if (isTieredGenericSupport(item)) return false;
  if (isGenericSupport(item)) return false;
  return item.rarity === "Gem";
}

/** Skill gems section — active skills only. */
export function isDisplayedInSkillGemsSection(item: Item): boolean {
  return isCharacterSkillGem(item);
}

/** Support gems section — Lineage supports only. */
export function isDisplayedInSupportGemsSection(item: Item): boolean {
  return isLineageSupportGem(item);
}

/** Only Lineage supports count toward character gear total and Apprise. */
export function shouldIncludeCharacterGemInPricing(item: Item): boolean {
  return isLineageSupportGem(item);
}

/** @deprecated Prefer isDisplayedInSkillGemsSection or isDisplayedInSupportGemsSection */
export function isNotableCharacterGem(item: Item): boolean {
  return isDisplayedInSkillGemsSection(item) || isDisplayedInSupportGemsSection(item);
}

export function filterNotableCharacterGems(gems: Item[]): Item[] {
  return gems.filter(isNotableCharacterGem);
}

export function filterCharacterGemsForPricing(gems: Item[]): Item[] {
  return gems.filter(shouldIncludeCharacterGemInPricing);
}

/**
 * Walk all gem candidates: top-level gems + inventory, plus supports nested in skill
 * socketed_items (e.g. Her Declaration socketed inside Purity of Ice).
 *
 * Recursion into socketed_items applies to both detail.gems and detail.inventory so that
 * lineage gems are reachable regardless of which bucket the parent skill ended up in.
 * Generic supports are still filtered by each predicate; this walker only broadens
 * the candidate set so lineage gems nested in skill socketed_items are reachable.
 *
 * Yields `[item, fromSocket]` where `fromSocket` is true for items that came from
 * a parent gem's socketed_items (e.g. skill gems inside a meta/spirit gem's trigger
 * slots).  This flag is used by `gemSourceLabel` to suppress the "From Weapon" label
 * on gems that are merely socketed in another gem rather than granted by equipment.
 */
export function* walkCharacterGemCandidates(
  detail: Pick<CharacterDetail, "gems" | "inventory">,
): Generator<[Item, boolean]> {
  for (const item of detail.gems ?? []) {
    yield [item, false];
    if (isCharacterSkillGem(item)) {
      for (const nested of item.socketed_items ?? []) yield [nested, true];
    }
  }
  for (const item of detail.inventory ?? []) {
    yield [item, false];
    if (isCharacterSkillGem(item)) {
      for (const nested of item.socketed_items ?? []) yield [nested, true];
    }
  }
}

/** A gem item together with context about where it was collected from. */
export interface GemEntry {
  item: Item;
  /** True when the gem came from socketedItems of a parent skill gem (e.g. a skill
   *  socketed into a meta/spirit gem's trigger slots). */
  fromSocket: boolean;
}

function collectGemsFromBuckets(
  detail: Pick<CharacterDetail, "gems" | "inventory">,
  predicate: (item: Item) => boolean,
): GemEntry[] {
  const seen = new Set<string>();
  const out: GemEntry[] = [];
  for (const [item, fromSocket] of walkCharacterGemCandidates(detail)) {
    if (!predicate(item)) continue;
    if (seen.has(item.id)) continue;
    seen.add(item.id);
    out.push({ item, fromSocket });
  }
  return out;
}

export function collectCharacterSkillGemsForDisplay(
  detail: Pick<CharacterDetail, "gems" | "inventory">,
): GemEntry[] {
  return collectGemsFromBuckets(detail, isDisplayedInSkillGemsSection);
}

export function collectCharacterSupportGemsForDisplay(
  detail: Pick<CharacterDetail, "gems" | "inventory">,
): GemEntry[] {
  return collectGemsFromBuckets(detail, isDisplayedInSupportGemsSection);
}

export function collectCharacterOtherInventory(
  detail: Pick<CharacterDetail, "inventory" | "gems">,
): Item[] {
  const displayedGemIds = new Set([
    ...collectCharacterSkillGemsForDisplay(detail).map((g) => g.item.id),
    ...collectCharacterSupportGemsForDisplay(detail).map((g) => g.item.id),
  ]);
  return (detail.inventory ?? []).filter(
    (item) =>
      !displayedGemIds.has(item.id) &&
      !isHiddenSocketSupport(item) &&
      item.inventory_id !== "Charm" &&
      !item.is_charm,
  );
}

/** Source label for a skill gem, based on inventory_id and whether it came from a socket.
 *
 * | inventory_id / context          | label          |
 * |---------------------------------|----------------|
 * | AscendancySkills                | "Ascendancy"   |
 * | null + fromSocket=true          | null (nested in meta/spirit gem socket) |
 * | null + fromSocket=false (inv.)  | "From Weapon"  |
 * | SkillSlots / DefaultAttackSkills / other | null  |
 */
export function gemSourceLabel(item: Item, fromSocket = false): string | null {
  const iid = item.inventory_id;
  if (iid === "AscendancySkills") return "Ascendancy";
  // Gems with no inventory_id that come DIRECTLY from the inventory bucket are
  // granted by equipped weapons.  Those nested in a meta gem's socketedItems
  // have fromSocket=true and must NOT be labelled "From Weapon".
  if (item.rarity === "Gem" && !iid && !fromSocket) return "From Weapon";
  return null;
}
