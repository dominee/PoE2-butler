# Item price estimates (PoE2, hybrid)

This product isn't affiliated with or endorsed by Grinding Gear Games in any way.

## Goals

- Show an **indicative** price in the item **detail pane** (in addition to bulk [poe.ninja](https://poe.ninja)-style lookups used for stash highlights).
- **Prefer third-party** economy APIs where they are accurate and cache-friendly.
- For rolled rares and other cases where aggregators do not have a good match, **fall back** to the public **Path of Exile 2 official trade JSON API** (not browser scraping): search, list results, and fetch listed items, then compute a **median** chaos equivalent.
- All estimates are **snapshots** of a thin slice of the market, not live guarantees.

## Tiers (lookup order)

| Tier | Source | Typical use |
|------|--------|-------------|
| A | poe.ninja (or `StaticPriceSource` in test) | Currency, uniques, bulk overview endpoints |
| B | Optional `Poe2ScoutSource` (disabled until a stable public URL is configured) | Placeholder for future community API integration |
| C | GGG `POST/GET` trade2 search + fetch (see [trade_deeplinks.md](trade_deeplinks.md)) | Rares, magic, or when tier A does not return a value |

## Trade parity and relaxation

- **Stat tolerance** matches the same “same item on trade” behaviour as `POST /api/trade/search` (`tolerance_pct`, same as user prefs; see [`backend/app/services/trade_url.py`](../backend/app/services/trade_url.py)).
- **Relaxation (overlay-style)**: if a search has **too few** comparable listings, relax by **dropping** stat filters in order: **crafted** → **enchant** → **rune** → **implicit** → **explicit**; within each group, **later** filters in the item’s mod list are dropped first. Stop when the reported `total` is at least a configured minimum (see `pricing_min_trade_listings`) or filters are exhausted.

## Median and display units

- Listing ask prices are normalised to **chaos** using live league rates (Divine, Exalted, etc.) from the same aggregator tier where possible.
- The displayed estimate uses the **median** of available listing chaos equivalents in the sample to reduce the effect of outliers.
- The API may also expose `divine` or `exalted` **denominations** in `PriceEstimate` when convenient for the UI, with `chaos_equiv` the canonical value for highlights.

## Asynchronous jobs

- A **refined** estimate (especially tier C) is scheduled on the **arq** worker and state is kept in **Redis** (`poe2b:price_job:*` keys).
- The client **polls** `GET /api/pricing/estimate/{job_id}`; duplicate requests for the same user + item + league de-duplicate to one job id.
- The worker applies third-party rate limits in `backend/app/services/third_party_ratelimit.py` (separate keys for GGG trade fetch vs poe.ninja).

## Rate limits and production behaviour

- GGG and community sites expect conservative request spacing and a clear **User-Agent** (this repo uses the same product + contact pattern as other GGG HTTP clients).
- Set `pricing_trade_estimate_enabled=0` to disable tier C entirely if you need to stay on aggregators only.

## Environment (see [deploy/env/.env.example](deploy/env/.env.example))

- `PRICING_TRADE_ESTIMATE_ENABLED` — allow tier C (default `1` in example).
- `PRICING_SCOUT_BASE_URL` — optional future tier B; empty disables.
- `PRICING_MIN_TRADE_LISTINGS` — stop relaxing when search `total` is at least this.
- `GGG_TRADE_FETCH_MIN_INTERVAL_SEC` — minimum delay between GGG search/fetch steps.

## Limitations

- **Stat id gaps**: if a mod cannot be mapped to a trade stat id, the search may be weaker; see [trade_deeplinks.md](trade_deeplinks.md).
- **Low liquidity** thin markets may yield `None` or wide uncertainty even after relaxation.
- **POE2Scout (tier B)**: a stable item-level HTTP contract must be agreed before turning on; the shipped adapter is a no-op when the base URL is empty.
