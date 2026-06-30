# Changelog

Notable **user-facing behavior** and **visual/UI** updates for Hideout Butler. Internal refactors, CI, and tooling are omitted unless they directly affect what players see or do in the app.

---

## 2026-06-30

### App · character gear snapshot timeline

- A **horizontal dot timeline** above the stat summary lists gear **change events** (up to **20** per character): dots appear only when items are added, removed, or modified — unchanged refreshes are not stored or shown.
- Each dot shows the **date and time** of the change plus a short **diff list** (+ new, ~ changed, − removed).
- Click a dot to browse **historic equipped gear**, stat summary, doll/table layouts, and item detail (including share links from that point in time).
- An amber banner marks historic view with **Back to current**; manual **Refresh** archives the previous snapshot before fetching new data.

---

## 2026-06-25

### Live GGG OAuth — characters (UAT and production)

- **Granted scopes:** `account:profile` and `account:characters` are live against real GGG in **UAT** and **production**. **Dev** still uses `mock-ggg/`.
- **PoE2 character API:** the backend calls `GET /character/poe2` (and per-character detail) using `GGG_API_REALM=poe2`. PoE1-style `/account/characters` paths are not used for PoE2.
- **Still blocked on GGG:** `account:stashes` (no PoE2 stash scope yet) and `account:leagues` (not granted). Stash tabs in UAT/prod remain unavailable until GGG adds a PoE2 stash scope; **league selection is inferred** from your character list (and `GGG_DEFAULT_LEAGUE` when needed). See [GGG_API.md](GGG_API.md).
- **OAuth callback:** duplicate browser callbacks (same `state`, new `code`) no longer log you out with `invalid_or_expired_state`; the second request reuses the session from the first.

### App · character gear — doll and table views

- The **Characters** pane offers **Doll** and **Table** layout toggles for equipped gear on the selected character.
- **Doll** shows a paper-doll grid (weapon, armour, rings, belt, etc.); **passive jewels** and filtered **skill gems** appear in sections below the doll.
- **Table** lists equipped gear plus jewels, gems, and other character items in one sortable grid (slot, name, base type, ilvl, mods).
- **Live GGG payloads:** equipment rows often expose slot as numeric `itemSlot` on the wrapper; the backend maps these to standard slot ids (`Helm`, `BodyArmour`, …) so armour and accessories classify correctly (wrapper metadata wins over stale inner `itemData.inventoryId` values such as `SkillSlots`).

### App · Runeforged / Runemastered items

- **Runeforged** league items (light blue in-game outline) use a matching **cyan border and glow** on item cards and in the detail pane, detected from GGG `frameTypeId`, a `runeforged` flag, or a `Runeforged` / `Runemastered` name prefix.

### App · league picker without `account:leagues`

- **`GET /api/leagues`** builds the league list from your **characters snapshot** when no leagues snapshot exists, so the header league dropdown works after login even without the leagues OAuth scope.
- **Refresh** updates `preferred_league` from character data when the stored value is missing or a permanent league placeholder.

### UAT environment

- **UAT** (`docker-compose.uat.yml`) now uses **live GGG OAuth2** — there is **no `mock-ggg` service** in that stack. Copy [deploy/env/.env.uat.example](deploy/env/.env.uat.example) and set real `GGG_CLIENT_ID` / `GGG_CLIENT_SECRET`. Runbook: [GGG_API.md §6.1](GGG_API.md) and [DEPLOY.md §4.6](DEPLOY.md).

### Testing (operators)

- Optional **live GGG integration tests** (`pytest -m live_ggg`) validate UAT credentials and endpoints; they are **excluded from default CI and `make test`** — run explicitly when the UAT stack is up. See [TESTS.md](TESTS.md).

---

## 2026-05-21

### App · weighted upgrade search

- The detail pane now offers **two upgrade search buttons** below the full-width "Trade Search" button: **Upgrade** (hard per-stat min values) and **Upgrade (weighted)** (weights mods by their current tier: T1=30, T2=20, T3=15, T4+=10).
- **GGG trade API limitation:** GGG's server-side trade2 API rejects `weight`-type stat groups from anonymous (non-browser) callers as "Query is too complex — logging in will increase this limit." This is a GGG constraint on unauthenticated server requests; the weight group base complexity exceeds the anonymous budget regardless of filter count. **When this rejection occurs, the backend automatically falls back to the regular upgrade search** (min-value `and` group) so you always receive a working trade URL instead of a blank search. The payload in clipboard still contains the weighted structure for reference. This limitation is tracked in [`docs/trade_deeplinks.md`](docs/trade_deeplinks.md).

### App · activity log — character gear diffs

- The **Activity** panel now includes a **Gear** section that shows new and changed equipped items across your characters, in addition to stash tab diffs. The `GET /api/activity` response includes a `gear_entries` field, and the total event count in the panel header reflects gear changes too.

### App · character stat quality %

- Each section in the **Character Stats** summary (Life/ES, Resistances, Offence, Defence) now shows a `PercentBar` indicating the average T1 quality of mods in that section — 100% means every roll in the section is at T1 maximum, values above 100% are possible for overrolls.

### App · roll quality bars — tier breakpoints and candle bars

- **Unique items**: roll bars continue to show a fill bar with tier breakpoint markers as subtle vertical lines.
- **Rare items**: each mod now shows a single **candle bar** — the segment covers the current tier's range (min → max) within the T1 scale, and a brighter marker indicates the actual roll position. This replaces the previous two-bar layout.
- Bars are now displayed for **rare items** whose mods were inferred from text when `extended.mods` is absent (the backend infers tier data from the RePoE mod ranges bundle in this case).
- The sub-row label was renamed from "This affix band:" to **"Range:"**, and the Roll/Range chart text is vertically aligned.

---

## 2026-04-29

### App · refined trade median (GGG)

- **Same item on trade** and the detail-pane **Refresh pricing** pipeline POST trade2 searches with **Instant Buyout** .
- **Refined estimates** are saved to the **database** when the worker finishes so the detail pane can reload them after you switch items or restart the app; **Apprise** (header) queues a capped stash-only backfill that fills **missing** estimates before refreshing **older** ones (`PRICING_BACKFILL_MAX_ITEMS`). **Refresh** updates inventory snapshots only and does not queue pricing.
- Listing samples use a **robust median** (upper-tail outlier resistance) over more fetched rows, and the fallback **mirror → chaos** conversion anchors on **divine** so mirror-tier asks do not collapse to a tiny chaos value.

### App · live currency rates (poe.ninja PoE2)

- **Header / trade conversion** now uses poe.ninja’s **PoE2** economy JSON when the PoE1-style URL fails or returns no data, and dev compose defaults to **`PRICING_BASE_URL=https://poe.ninja`**. If your env still has `…/api/data`, you get an automatic PoE2 fallback for currency so Fate of the Vaal (and similar) no longer stick on placeholder div/ex/chaos numbers.

## 2026-04-28

### GGG trade2 rate limiting (server)

- **Global Redis lock** coordinates every trade2 **search POST**, **list GET**, and **fetch GET** (price-estimate worker and “open on trade” style API). After each successful response, the lock enforces **minimum interval + extra spacing** (configurable, see `deploy/env/.env.example`). On **HTTP 429**, the lock TTL follows GGG’s “Please wait *N* seconds” message (plus buffer, with fallback and a maximum cap) so the stack backs off instead of retrying immediately.

### App · refined price estimate

- The detail pane **does not** automatically start a background refined estimate when you select an item; use **Refresh pricing** (or equivalent) to enqueue work.

### Admin console

- **Overview:** optional dashboard polling is **not** started automatically when `ADMIN_DASHBOARD_REFRESH_SEC` is set; use **Refresh now** or **Start auto-refresh**. The **Throttles** table shows GGG lock state; **Sample jobs** includes an **Updated** column (last job state write, UTC).

---

## 2026-04-26

### Trade site (PoE2)

- **“Open on trade” / trade search** now builds PoE2 trade URLs and POST bodies that match the live trade site flow, including league in the path and documented in-repo behavior (see `docs/trade_deeplinks.md`).
- **Stat filters** on generated searches are aligned with GGG’s stat index: mods are matched to the correct `implicit` / `explicit` / `rune` / `enchant` / `crafted` buckets, with a bundled fallback when the live stats catalogue is unavailable.
- **Rarity and uniques**: rarity is applied correctly in trade queries; unique items use `query.name` where appropriate so the trade UI opens on the intended listing.
- **Mod text parsing** strips GGG-style tags from mod lines so roll filters resolve reliably against the stat catalogue.

### Mock GGG sign-in and characters (development)

- **Live Poe.ninja snapshots**: the mock GGG service can load real character models from Poe.ninja for URLs listed in `mock-ggg/config/poe_ninja_characters.toml`, so development sign-in can mirror real accounts and leagues instead of only static JSON.
- **Mock login list**: the ExileOne-only static profile was removed; OAuth choices are driven by the TOML URL list (with optional extra rows from `static_users.json` if you add them). With `MOCK_GGG_SKIP_POE_NINJA=1` (tests), Poe.ninja HTTP is skipped but the same TOML accounts still appear; gear is seeded from `characters.json` where character names match.
- **Leagues and TOML**: league slugs such as `vaalssf` are parsed correctly; a malformed TOML array (e.g. missing comma between URL strings) no longer silently drops every ninja account from the login dropdown.
- **Stash preview for ninja-backed users**: the first load of a stash tab shows equipped gear packed into the mock stash (previous snapshot is populated so the tab is not empty on first open).

### Item UI and stash visuals

- **Roll bars (`PercentBar`)**: roll strength indicators use the app theme (ink → ember gradient and consistent accent colors) instead of generic chart colors.
- **Favicons on `main`** (commit `1fdf60a`, not yet on the `dev` line at the time of this log): item detail, export preview, and stash icon grids use **rarity-colored favicons** derived from item frame type, with shared helpers and tests for consistent icons across stash and detail views.

---

## Earlier

Prior user-visible changes are not listed here; use `git log` on `main` for full history.
