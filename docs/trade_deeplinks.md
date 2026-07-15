# PoE2 Trade deep links (official site)

This product isn't affiliated with or endorsed by Grinding Gear Games in any way.

## What the app does

The **Same item on trade** and **Upgrade search** actions call `POST /api/trade/search`. The backend builds a PoE2-shaped `query` + `sort`, then **POSTs** that JSON to Grinding Gear Games' public trade API to obtain a short-lived **search id** (and, for tier C / internal callers, the full **POST** JSON including the first **`result`** page). The response `url` opens the official trade UI:

`https://www.pathofexile.com/trade2/search/poe2/<league>/<search_id>`

If the POST fails (network error, HTTP error, malformed JSON, or missing `id`), the API **falls back** to the league-only URL (`…/poe2/<league>`) so the SPA still opens a useful page. The clipboard continues to receive the full internal payload (including `mode`, `tolerance_pct`, and per-mod `text` / `template`) for debugging or manual reuse.

## GGG API contract (PoE2)

Verified against `https://www.pathofexile.com/api/trade2/search` (2026):

| Piece | Detail |
|--------|--------|
| **Create search** | `POST {trade_search_api_base}/{url-encoded-league}` with JSON body `{ "query": { … }, "sort": { … } }`. Default base: `https://www.pathofexile.com/api/trade2/search`. |
| **Response** | JSON object with string `id`, optional `result` (first page of listing id strings), `total`, etc. |
| **Browser URL** | `https://www.pathofexile.com/trade2/search/poe2/{league}/{id}` — same `id` as returned by POST. |
| **Base item** | PoE2 expects the item base name as a **plain string** in `query.type` (e.g. `"Dualstring Bow"`). The older PoE1-style `filters.type_filters.filters.type.option` object is **invalid** here and yields `400 Invalid query`. |
| **Unique name** | For `rarity: unique`, set `query.name` to the unique's display name (e.g. `"Headhunter"`) together with `query.type` as the base (e.g. `"Heavy Belt"`). Without `name`, the trade site matches every item of that base. |
| **Status (Instant Buyout)** | `POST` bodies must use **top-level** `query.status.option = "securable"`. Putting `status_filters` under `query.filters` returns `400 Unknown filter group: status_filters` (that id is only the filter-metadata grouping from `GET /api/trade2/data/filters`). We omit `trade_filters.sale_type` with JSON `null` for "Buyout or Fixed Price": GGG returns `Invalid sale type`; securable scope already targets instant-buyout listings. |
| **Rarity** | `query.filters.type_filters.filters.rarity.option` uses only GGG-supported values: `normal`, `magic`, `rare`, `unique`, `uniquefoil`, `nonunique`. The `type_filters` group sets `disabled: false`. Currency, gems, divination cards, and quest items have **no** rarity filter (those strings are not valid trade rarity options). |
| **Corruption** | `query.filters.misc_filters.filters.corrupted.option` and `twice_corrupted.option` are set explicitly to `"true"` or `"false"` from the item (never omitted / `"Any"`). Matches GGG `misc_filters` metadata from `GET /api/trade2/data/filters`. |
| **Socket count** | Items with sockets include a socket count filter so the search does not mix populations with different socket counts (exceptional uncorrupted extra sockets are far rarer and priced differently than corrupted ones). **Gear**: `query.filters.equipment_filters.filters.rune_sockets` (renamed "Augmentable Sockets" in PoE2 0.4.0; filter id unchanged). **Skill gems**: `query.filters.misc_filters.filters.gem_sockets`. Exact search: `min = max = count`. Upgrade search: `min = count` only. Items with 0 sockets omit the filter. Both ids confirmed from `GET /api/trade2/data/filters`. |
| **Stats** | `query.stats` is a list of blocks `{ "type": "and", "filters": [ … ] }`. Each filter uses GGG stat ids like `explicit.stat_<numeric_hash>` and optional `value` `{ "min", "max" }`. Implicit / explicit / rune / enchant prefixes differ (`implicit.stat_…`, `rune.stat_…`, etc.). |
| **Poll results** | `GET https://www.pathofexile.com/api/trade2/search/{league}/{id}` may return only `id` + echoed `query` (no `result` / `total`) for programmatic clients. **Use the `result` array from the successful `POST` response** as the first page of listing ids. Optional: paginate with `GET …?start=N` when the API includes `result` (e.g. null slots); the hybrid price worker uses POST ids first, then falls back to GET paging. |
| **Fetch item JSON** | `GET https://www.pathofexile.com/api/trade2/fetch/{id1},{id2},...?query={search_id}` returns full listing payloads (include `listing.price`). Batches are small (typically up to ~10 ids per request). Same `User-Agent` as other GGG trade calls. |

## Stat id resolution

Before POSTing, `backend/app/services/trade_stat_index.py` loads `GET {trade_stats_data_url}` (default `https://www.pathofexile.com/api/trade2/data/stats`) once per process and matches each mod's `#`-placeholder **template** (plus mod **bucket**: implicit / explicit / rune / enchant / crafted) to the correct `explicit.stat_<hash>` / `implicit.stat_<hash>` / … id. A small bundled map remains as a fallback when the download fails or a line is missing from the catalogue.

## User-Agent

All server-side calls to GGG trade endpoints use the same identifiable pattern as other GGG HTTP clients in this repo (OAuth client id, version, contact `dev@hell.sk`, product suffix). See `trade_search_user_agent()` in `backend/app/services/trade_stat_catalog.py`.

## Server-side rate limiting (this repo)

`POST` (create search), optional **`GET`** (list / paging when `result` is present), and **`GET`** (fetch listings) share a **global Redis lock** so all callers (hybrid **price** worker, **trade search** API) serialize against GGG's trade2 limits. Waits, success spacing, and **HTTP 429** backoffs are implemented in `third_party_ratelimit.py` and wired from `submit_trade_search` / `trade_listings.py`. Configure via `GGG_TRADE_*` in `deploy/env/.env.example`. Operational visibility: admin **Overview** → throttle rows and [pricing_estimates.md](pricing_estimates.md) § *GGG trade2 rate limiting*.

## Sanitized POST body

`backend/app/services/trade_ggg_body.py` implements `ggg_search_body_from_result_payload()`, which:

- Copies `query` and `sort` from the internal payload.
- Removes app-only keys accidentally nested under `query` (`mode`, `tolerance_pct`).
- For each stat filter, keeps only `id`, `value`, and `disabled` — dropping `bucket`, `text`, and `template` used for UI / clipboard.

## Search modes

`POST /api/trade/search` accepts a `mode` field:

| Mode | Behaviour |
|------|-----------|
| `exact` | Builds per-stat `min`/`max` filters at `±tolerance_pct` of the current roll, using an `and` stat group. |
| `upgrade` | Builds per-stat `min` floors at 95 % of the current roll, using an `and` stat group. |
| `weighted_upgrade` | Assigns tier-based weights (T1=30, T2=20, T3=15, T4+=10) to the top mods and attempts a GGG `weight` stat group with floor `⌊Σ(baseline × weight) × 0.85⌋`. **Falls back automatically** to `upgrade` behaviour on HTTP 400 (see below). |

### GGG weight-group complexity limit

GGG's trade2 API enforces a **query complexity budget** that is **significantly lower for unauthenticated (server-side) callers** than for logged-in browser sessions. The `weight` stat-group type carries a high base complexity that exceeds the anonymous budget regardless of filter count — `and` groups with six filters (GGG-reported complexity 14) are accepted, while `weight` groups with as few as three filters are rejected:

```
HTTP 400  {"error":{"code":2,"message":"Query is too complex. Please reduce the amount of filters used.\nLogging in will increase this limit."}}
```

**Backend behaviour:** `submit_trade_search` returns a 4-tuple `(search_id, data, rate_limited, status_code)`. When `status_code == 400`, the `weighted_upgrade` handler in `backend/app/api/trade.py` logs `trade_search.weighted_upgrade_fallback` and retries as a regular `upgrade` (`and`) search, which is then returned to the caller. The frontend opens the fallback URL transparently; the clipboard payload retains the original weighted structure.

**Future improvement:** attach the user's GGG OAuth access token to the POST request headers — authenticated users receive a higher complexity limit ("Logging in will increase this limit"). This would require decrypting `UserToken.access_token` and forwarding it as `Authorization: Bearer <token>` on the `/api/trade2/search` call.

## Testing without hitting GGG

CI and local unit tests **must not** depend on live GGG responses:

- **Body shaping**: `backend/tests/test_trade_ggg_body.py`, `backend/tests/test_trade_url.py`.
- **HTTP submit**: `backend/tests/test_trade_search_submit.py` patches `httpx.AsyncClient` (assert on `(search_id, post_json, rate_limited, status_code)` from `submit_trade_search`).
- **Route**: `backend/tests/test_auth_flow.py` patches `ensure_trade_stats_index` and `submit_trade_search` (4-tuple) so CI does not call GGG.

## Limitations

- **Browser vs API**: Opening the trade **website** in a normal browser may hit Cloudflare challenges; that is separate from the JSON search API used here. Automated "open in browser" checks are not used in tests.
- **403 / rate limits**: Some networks or User-Agents may be rejected. The fallback URL keeps the feature usable.
- **Stat coverage**: Mod lines only appear in the POST body when a trade stat id can be resolved (catalogue + bundled fallback). Unusual or new mods may still be missing until GGG's stats export includes them.
- **Weight group (anonymous callers)**: GGG rejects `weight` stat groups from server-side requests due to query complexity limits. The app falls back to a min-floor `upgrade` search automatically. See *GGG weight-group complexity limit* above.
