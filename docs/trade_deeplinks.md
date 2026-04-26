# PoE2 Trade deep links (official site)

This product isn't affiliated with or endorsed by Grinding Gear Games in any way.

## What the app does

The **Same item on trade** and **Upgrade search** actions call `POST /api/trade/search`. The backend builds a PoE2-shaped `query` + `sort`, then **POSTs** that JSON to Grinding Gear Games’ public trade API to obtain a short-lived **search id**. The response `url` opens the official trade UI:

`https://www.pathofexile.com/trade2/search/poe2/<league>/<search_id>`

If the POST fails (network error, HTTP error, malformed JSON, or missing `id`), the API **falls back** to the league-only URL (`…/poe2/<league>`) so the SPA still opens a useful page. The clipboard continues to receive the full internal payload (including `mode`, `tolerance_pct`, and per-mod `text` / `template`) for debugging or manual reuse.

## GGG API contract (PoE2)

Verified against `https://www.pathofexile.com/api/trade2/search` (2026):

| Piece | Detail |
|--------|--------|
| **Create search** | `POST {trade_search_api_base}/{url-encoded-league}` with JSON body `{ "query": { … }, "sort": { … } }`. Default base: `https://www.pathofexile.com/api/trade2/search`. |
| **Response** | JSON object with string `id` (and `result`, `total`, etc.). |
| **Browser URL** | `https://www.pathofexile.com/trade2/search/poe2/{league}/{id}` — same `id` as returned by POST. |
| **Base item** | PoE2 expects the item base name as a **plain string** in `query.type` (e.g. `"Dualstring Bow"`). The older PoE1-style `filters.type_filters.filters.type.option` object is **invalid** here and yields `400 Invalid query`. |
| **Unique name** | For `rarity: unique`, set `query.name` to the unique’s display name (e.g. `"Headhunter"`) together with `query.type` as the base (e.g. `"Heavy Belt"`). Without `name`, the trade site matches every item of that base. |
| **Rarity** | `query.filters.type_filters.filters.rarity.option` uses only GGG-supported values: `normal`, `magic`, `rare`, `unique`, `uniquefoil`, `nonunique`. The `type_filters` group sets `disabled: false`. Currency, gems, divination cards, and quest items have **no** rarity filter (those strings are not valid trade rarity options). |
| **Stats** | `query.stats` is a list of blocks `{ "type": "and", "filters": [ … ] }`. Each filter uses GGG stat ids like `explicit.stat_<numeric_hash>` and optional `value` `{ "min", "max" }`. Implicit / explicit / rune / enchant prefixes differ (`implicit.stat_…`, `rune.stat_…`, etc.). |
| **Poll results** | `GET https://www.pathofexile.com/api/trade2/search/{league}/{id}` returns listing keys; not used by Hideout Butler today. |

## Stat id resolution

Before POSTing, `backend/app/services/trade_stat_index.py` loads `GET {trade_stats_data_url}` (default `https://www.pathofexile.com/api/trade2/data/stats`) once per process and matches each mod’s ``#``-placeholder **template** (plus mod **bucket**: implicit / explicit / rune / enchant / crafted) to the correct `explicit.stat_<hash>` / `implicit.stat_<hash>` / … id. A small bundled map remains as a fallback when the download fails or a line is missing from the catalogue.

## User-Agent

All server-side calls to GGG trade endpoints use the same identifiable pattern as other GGG HTTP clients in this repo (OAuth client id, version, contact `dev@hell.sk`, product suffix). See `trade_search_user_agent()` in `backend/app/services/trade_stat_catalog.py`.

## Sanitized POST body

`backend/app/services/trade_ggg_body.py` implements `ggg_search_body_from_result_payload()`, which:

- Copies `query` and `sort` from the internal payload.
- Removes app-only keys accidentally nested under `query` (`mode`, `tolerance_pct`).
- For each stat filter, keeps only `id`, `value`, and `disabled` — dropping `bucket`, `text`, and `template` used for UI / clipboard.

## Testing without hitting GGG

CI and local unit tests **must not** depend on live GGG responses:

- **Body shaping**: `backend/tests/test_trade_ggg_body.py`, `backend/tests/test_trade_url.py`.
- **HTTP submit**: `backend/tests/test_trade_search_submit.py` patches `httpx.AsyncClient`.
- **Route**: `backend/tests/test_auth_flow.py` patches `ensure_trade_stats_index` and `submit_trade_search` so CI does not call GGG.

## Limitations

- **Browser vs API**: Opening the trade **website** in a normal browser may hit Cloudflare challenges; that is separate from the JSON search API used here. Automated “open in browser” checks are not used in tests.
- **403 / rate limits**: Some networks or User-Agents may be rejected. The fallback URL keeps the feature usable.
- **Stat coverage**: Mod lines only appear in the POST body when a trade stat id can be resolved (catalogue + bundled fallback). Unusual or new mods may still be missing until GGG’s stats export includes them.
