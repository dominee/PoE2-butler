export type ItemRarity =
  | "Normal"
  | "Magic"
  | "Rare"
  | "Unique"
  | "Currency"
  | "Gem"
  | "DivinationCard"
  | "QuestItem";

export interface ItemProperty {
  name: string;
  value: string | null;
}

export interface Socket {
  group: number;
  type: string;
}

export interface ModMagnitude {
  hash: string;
  min: number | null;
  max: number | null;
  /** T1 maximum from the bundled mod DB. Null when data is unavailable. */
  t1_max: number | null;
}

/** Per-modifier metadata from GGG ``extended.mods``.  Present only when the
 *  GGG API returns the extended object; otherwise the array is empty. */
export interface ModDetail {
  name: string;
  tier: number | null; // 1 = T1 (best)
  level: number | null;
  magnitudes: ModMagnitude[];
}

export interface Item {
  id: string;
  inventory_id: string | null;
  w: number;
  h: number;
  x: number | null;
  y: number | null;
  /** GGG / extended: armour class, ring, etc. (PoE2 item text) */
  item_class?: string | null;
  name: string;
  type_line: string;
  base_type: string;
  rarity: ItemRarity;
  ilvl: number | null;
  identified: boolean;
  corrupted: boolean;
  properties: ItemProperty[];
  requirements: ItemProperty[];
  implicit_mods: string[];
  /** Per implicit when GGG returns ``extended.mods.implicit`` (same shape as explicit). */
  implicit_mod_details: ModDetail[];
  explicit_mods: string[];
  explicit_mod_details: ModDetail[];
  socketed_items: Item[];
  rune_mods: string[];
  enchant_mods: string[];
  crafted_mods: string[];
  sockets: Socket[];
  stack_size: number | null;
  max_stack_size: number | null;
  icon: string | null;
  /** Normalized from the API (GGG `flavourText` / US `flavorText` parsed in the backend). */
  flavour_text?: string | null;
  /**
   * Wiki / community “type” roll range, parallel to each implicit (same order). Empty when
   * unknown or not a bundled unique. Not a per-snapshot GGG field.
   */
  implicit_mod_range_hints?: (string | null)[];
  /**
   * Same for explicit mods, parallel to explicit_mods.
   */
  explicit_mod_range_hints?: (string | null)[];
  /** If present, raw GGG camelCase (some clients); detail pane also reads this. */
  flavourText?: string | null;
  flavorText?: string | null;
  trailer_note?: string | null;
}

export interface CharacterSummary {
  id: string;
  name: string;
  realm: string;
  class: string;
  level: number;
  league: string | null;
  experience: number | null;
}

/** Rolled-up mod line from equipment (template key + one or more numbers). */
export interface StatRow {
  key: string;
  label: string;
  values: number[];
  value_shape?: "auto";
}

export interface StatSection {
  id: string;
  label: string;
  sort_index: number;
  rows: StatRow[];
}

/** Per-section mod rollups from the backend; see `stat_summary` domain. */
export interface EquipmentStatSummary {
  sections: StatSection[];
}

export interface CharacterDetail {
  summary: CharacterSummary;
  equipped: Item[];
  inventory: Item[];
  /** Templated mod rollups (all numeric mod lines, grouped by section heuristics). */
  stat_summary?: EquipmentStatSummary;
}

export interface League {
  id: string;
  realm: string;
  description: string | null;
  current: boolean;
}

export interface LeaguesResponse {
  leagues: League[];
  current: string | null;
  preferred: string | null;
}

export interface CharactersResponse {
  league: string | null;
  characters: CharacterSummary[];
}

export interface Me {
  id: string;
  account_name: string;
  realm: string;
  preferred_league: string | null;
  trade_tolerance_pct: number;
}

export interface RefreshResponse {
  profile: boolean;
  leagues: boolean;
  characters: boolean;
  errors: string[];
}

export interface TradeSearchResponse {
  mode: "exact" | "upgrade";
  league: string;
  url: string;
  payload: Record<string, unknown>;
  tolerance_pct?: number | null;
}

export interface ItemTextResponse {
  text: string;
}

export interface CreateShareResponse {
  share_id: string;
  public_path: string;
}

/** Response from `GET /api/public/items/{share_id}` (unauthenticated). */
export interface PublicItemResponse {
  league: string;
  item: Item;
}

export interface Prefs {
  trade_tolerance_pct: number;
  preferred_league: string | null;
  valuable_threshold_chaos: number;
}

export interface PriceEstimate {
  value: number;
  unit: "chaos" | "divine" | "exalted";
  chaos_equiv: number;
  source: string;
  confidence: number;
  note: string | null;
}

export interface PricingResponse {
  league: string;
  prices: Record<string, PriceEstimate | null>;
}

export interface StashColour {
  r: number;
  g: number;
  b: number;
}

export interface StashTabSummary {
  id: string;
  name: string;
  type: string;
  index: number;
  colour: StashColour | null;
}

export interface StashListResponse {
  league: string;
  tabs: StashTabSummary[];
}

export interface StashTab {
  tab: StashTabSummary;
  items: Item[];
}

// ── cross-tab search ──────────────────────────────────────────────────────────

export interface StashSearchResult {
  tab_id: string;
  tab_name: string;
  tab_index: number;
  items: Item[];
}

export interface StashSearchResponse {
  league: string;
  query: string;
  results: StashSearchResult[];
  total_items: number;
}

// ── activity log ──────────────────────────────────────────────────────────────

export interface ChangedItem {
  old: Item;
  new: Item;
}

export interface ActivityEntry {
  tab_id: string;
  tab_name: string;
  new_items: Item[];
  changed_items: ChangedItem[];
  removed_items: Item[];
}

export interface ActivityResponse {
  league: string;
  has_prev: boolean;
  total_new: number;
  total_changed: number;
  entries: ActivityEntry[];
}
