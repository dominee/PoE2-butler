# Changelog

Notable **user-facing behavior** and **visual/UI** updates for PoE2 Butler. Internal refactors, CI, and tooling are omitted unless they directly affect what players see or do in the app.

---

## 2026-04-29

### App · refined trade median (GGG)

- **Same item on trade** and the detail-pane **Refresh pricing** pipeline POST trade2 searches with **Instant Buyout** .
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
