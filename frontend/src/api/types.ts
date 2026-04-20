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

export interface CharacterDetail {
  summary: CharacterSummary;
  equipped: Item[];
  inventory: Item[];
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
