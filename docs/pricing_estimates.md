# Item price estimates (PoE2, hybrid)

This product isn't affiliated with or endorsed by Grinding Gear Games in any way.

## Goals

- Show an **indicative** price in the item **detail pane** (in addition to bulk [poe.ninja](https://poe.ninja)-style lookups used for stash highlights).
- **Prefer third-party** economy APIs where they are accurate and cache-friendly.
- For rolled rares and other cases where aggregators do not have a good match, **fall back** to the public **Path of Exile 2 official trade JSON API** (not browser scraping): **POST** search (first page of listing ids in the response), **GET** fetch for listing payloads, then compute a **median** chaos equivalent.
- All estimates are **snapshots** of a thin slice of the market, not live guarantees.

## Tiers (lookup order)

| Tier | Source | Typical use |
|------|--------|-------------|
| A | poe.ninja (or `StaticPriceSource` in test) | PoE2: ``/poe2/api/economy/exchange/current/overview`` (``PRICING_BASE_URL=https://poe.ninja``); PoE1 mirrors: ``…/api/data`` + ``currencyoverview`` / ``itemoverview`` |
| B | Optional `Poe2ScoutSource` (disabled until a stable public URL is configured) | Placeholder for future community API integration |
| C | GGG trade2 **POST** search + **GET** fetch (see [trade_deeplinks.md](trade_deeplinks.md)) | Rares, magic, or when tier A does not return a value |

## Trade parity and relaxation

- **Stat tolerance** matches the same “same item on trade” behaviour as `POST /api/trade/search` (`tolerance_pct`, same as user prefs; see [`backend/app/services/trade_url.py`](../backend/app/services/trade_url.py)).
- **Relaxation (overlay-style)**: if a search has **too few** comparable listings, relax by **dropping** stat filters in order: **crafted** → **enchant** → **rune** → **implicit** → **explicit**; within each group, **later** filters in the item’s mod list are dropped first. Stop when the reported `total` is at least a configured minimum (see `pricing_min_trade_listings`) or filters are exhausted.

## Tier C: listing ids and fetch (implementation)

- **`submit_trade_search`** ([`trade_search_submit.py`](../backend/app/services/trade_search_submit.py)) returns **`(search_id, post_json, rate_limited)`** on success. The PoE2 trade2 **POST** body includes the first page of listing id strings in **`result`** plus **`total`**.
- The hybrid engine ([`estimate_engine.py`](../backend/app/services/pricing/estimate_engine.py)) parses ids with **`trade_listing_ids_from_search_post`** in [`trade_listings.py`](../backend/app/services/trade_listings.py). If **`POST`** did not yield string ids (rare), it falls back to **`trade_search_collect_string_ids`**, which **GET**s `…/search/{league}/{id}` with `?start=` paging when the response includes a `result` array (e.g. all-null first window).
- **`GET …/fetch/{ids}?query={search_id}`** loads full listing JSON (prices). Batching stays small to respect GGG limits.

## Median and display units

- Listing ask prices are normalised to **chaos** using live league rates (Divine, Exalted, etc.) from **poe.ninja** when that source is active and returns data (PoE2 exchange overview, league name or economy slug from [`/poe2/api/data/index-state`](https://poe.ninja/poe2/api/data/index-state)); otherwise **`trade_currency_chaos_fallback`** supplies approximate chaos values for GGG’s compact `listing.price.currency` ids (see `TRADE_LISTING_*` in [`deploy/env/.env.example`](../deploy/env/.env.example))).
- The displayed estimate uses a **robust median** of instant-buyout listing chaos equivalents (upper-tail outlier resistance) over a batched sample; see `trade_listings.median_chaos_robust` and `docs/trade_deeplinks.md`.
- The API may also expose `divine` or `exalted` **denominations** in `PriceEstimate` when convenient for the UI, with `chaos_equiv` the canonical value for highlights.

## Asynchronous jobs, Redis, and Postgres persistence

- A **refined** estimate (especially tier C) is scheduled on the **arq** worker. **In-flight** state is stored in **Redis** at `poe2b:price_job:{uuid}` as JSON (`PriceJobState`).
- Every `save_job_state` write sets **`updated_at`** to the current time (UTC ISO-8601) for observability.
- When a job reaches a **terminal** state (`completed` or `failed`), the worker **upserts** a row in **`item_price_estimates`** (unique on `user_id` + `league` + `item_id`) so the result survives Redis TTL and app restarts. The stored **`tolerance_pct`** must match the client query for `GET /api/pricing/estimate/item` to return that row (**204** if missing or tolerance changed).
- The client **polls** `GET /api/pricing/estimate/{job_id}` after `POST /api/pricing/estimate`. Duplicate POSTs for the same user + item + league de-duplicate to one job id via `poe2b:price_dedup:*`.
- **UI:** on opening the detail pane, the SPA **GETs** `/api/pricing/estimate/item` first (TanStack `persisted-price-estimate`); **POST** runs only after **Refresh pricing** (increments `rerunKey` in `useRefinedPriceEstimate`).
- **Apprise** (`POST /api/pricing/apprise`) enqueues **`backfill_item_price_estimates`** for **stash tabs only** in the chosen league: up to **`PRICING_BACKFILL_MAX_ITEMS`** (default 40) hybrid runs, **items with no DB row first**, then **oldest `computed_at`**. Before each hybrid run starts, the worker writes that batch to Redis with **`status: queued`** so the admin **Price queue** lists the full backlog (not only the single **running** item). Header **Refresh** (`POST /api/refresh`) updates snapshots only and **does not** queue pricing.
- **Concurrency:** at most **`PRICING_MAX_CONCURRENT_ESTIMATES`** (default **1**) hybrid runs execute trade work at once, via Redis slots `tp3:price_estimate:slot:*`. Additional jobs stay **`queued`** with message “Waiting for price estimate slot”. The arq worker **`ARQ_MAX_JOBS`** default is **2** (was 4) so unrelated jobs can still progress without spawning many parallel `price_estimate_item` workers.

## GGG trade2 rate limiting (critical)

Implementation: [`backend/app/services/third_party_ratelimit.py`](../backend/app/services/third_party_ratelimit.py) and call sites in [`trade_search_submit.py`](../backend/app/services/trade_search_submit.py), [`trade_listings.py`](../backend/app/services/trade_listings.py), and [`estimate_engine.py`](../backend/app/services/pricing/estimate_engine.py).

- **One global lock** in Redis: key `tp3:ggg_trade:lock`. Before any trade2 HTTP call, the process **awaits** this lock to expire (spacing or 429 cooldown).
- After each **HTTP 200**, the lock is set for **`ceil(ggg_trade_min_interval_sec + ggg_trade_extra_spacing_sec)`** seconds (integer seconds, at least 1). Defaults in code skew conservative; adjust via env in production.
- On **HTTP 429**, the response body is parsed for `Please wait N seconds`. The lock is set for **`min(N + buffer, max_cap)`** seconds, with a **fallback** if the message cannot be parsed, and a **hard cap** to avoid unbounded waits.
- The same lock applies to **trade search** from the app (`POST /api/trade/search` → `submit_trade_search`, which returns the POST JSON for tier C) so UI and workers do not each run independent burst traffic.

The admin **Overview** → **Price jobs (background)** section lists throttle keys (including `ggg_trade2_lock` PTTL) and a **Sample jobs** table with an **Updated** column reflecting `updated_at` from Redis.

## Other third-party throttling

- poe.ninja and other vendors use separate Redis keys in `third_party_ratelimit.py` (`tp3:*:next`); they are **not** the same as the GGG trade2 global lock.

## Environment (see [deploy/env/.env.example](../deploy/env/.env.example))

| Variable | Role |
|----------|------|
| `PRICING_TRADE_ESTIMATE_ENABLED` | `0` disables tier C; aggregators / lookup still work |
| `PRICING_SCOUT_BASE_URL` | Optional future tier B; empty disables |
| `PRICING_MIN_TRADE_LISTINGS` | Stop relaxing when search `total` ≥ this |
| `PRICING_BACKFILL_MAX_ITEMS` | Cap for hybrid estimates queued by **Apprise** (`POST /api/pricing/apprise`; missing rows first, then oldest) |
| `GGG_TRADE_MIN_INTERVAL_SEC` | Base part of the post-success lock TTL (alias: `GGG_TRADE_FETCH_MIN_INTERVAL_SEC`) |
| `GGG_TRADE_EXTRA_SPACING_SEC` | **Added** to the min interval for the post-success lock (default 5) |
| `GGG_TRADE_429_BUFFER_SEC` | Added to GGG’s parsed “wait N seconds” on 429 |
| `GGG_TRADE_429_FALLBACK_SEC` | Lock TTL if the 429 body does not include a parseable wait (default 300) |
| `GGG_TRADE_429_MAX_WAIT_SEC` | Upper bound for the 429 lock TTL |

## Production behaviour

- GGG and community sites expect conservative spacing and a clear **User-Agent** (this repo uses the same product + contact pattern as other GGG HTTP clients).
- If tier C is too aggressive for your deployment, set `PRICING_TRADE_ESTIMATE_ENABLED=0` or raise `GGG_TRADE_*` values.

## Limitations

- **Stat id gaps**: if a mod cannot be mapped to a trade stat id, the search may be weaker; see [trade_deeplinks.md](trade_deeplinks.md).
- **Low liquidity** thin markets may yield `None` or wide uncertainty even after relaxation.
- **POE2Scout (tier B)**: a stable item-level HTTP contract must be agreed before turning on; the shipped adapter is a no-op when the base URL is empty.
