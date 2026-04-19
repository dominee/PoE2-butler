# Bot-facing API contract

This document is the **frozen contract** between the PoE2 Hideout Butler backend
and third-party consumers such as the future Discord bot. Anything listed here
is a stable, supported surface. Endpoints that exist in the OpenAPI schema but
are _not_ listed here (for example anything under `/api/refresh`, `/api/trade`,
`/api/prefs`) are user-facing and may change without notice.

The canonical machine-readable schema is always `GET /openapi.json` on the live
backend, with a pinned snapshot at [`openapi.json`](./openapi.json) in this
repository.

## Authentication model for bots

The user-facing web UI uses session cookies + CSRF. Bots will use a different
path:

1. The user links their PoE2 Butler account with the Discord bot via a
   Discord-side slash command; the bot redirects them to
   `https://app.<domain>/link-bot?state=<opaque>` (frontend flow — not part of
   this contract).
2. After consent, the backend issues a long-lived, scoped **bot access token**
   (planned for a later milestone, out of scope for M6).
3. Bots include it as `Authorization: Bearer <token>` on every request.

For M6 the contract is **read-only from the perspective of the bot**; no
state-changing endpoints are exposed to bot tokens.

## Versioning

- API version is exposed in `info.version` of the OpenAPI schema.
- Any breaking change to an endpoint listed below bumps the minor version and
  is announced at least 14 days in advance in `CHANGELOG.md`.
- Additive changes (new optional fields, new endpoints) are non-breaking.

## Stable endpoints

All bot-stable endpoints are under `/api/` and return `application/json`. All
timestamps are ISO-8601 UTC.

### `GET /healthz`

Liveness probe. Always returns `{"status": "ok"}` with `200`.

### `GET /readyz`

Readiness probe. Returns `{"status": "ok"}` when database + Redis are reachable,
`503` otherwise.

### `GET /api/me`

Current linked account. Requires session cookie (users) or bearer token (bots).

```json
{
  "account_name": "Exile#1234",
  "preferred_league": "Standard",
  "trade_tolerance_pct": 15,
  "valuable_threshold_chaos": 100
}
```

### `GET /api/leagues`

Leagues visible to the linked account, from the latest profile snapshot.

```json
{
  "leagues": [
    {"id": "Standard", "realm": "poe2", "is_event": false},
    {"id": "Dawn of the Hunt", "realm": "poe2", "is_event": true}
  ],
  "current": "Dawn of the Hunt"
}
```

### `GET /api/characters?league=<id>`

Character summary list. `league` is optional; defaults to the user's preferred
league.

```json
{
  "characters": [
    {
      "name": "ButlerOfTheHideout",
      "class_name": "Warrior",
      "level": 92,
      "league": "Dawn of the Hunt",
      "experience": 1234567890
    }
  ]
}
```

### `GET /api/characters/{name}`

Full character detail including equipped items. The `items` payload uses the
normalized shape defined in `backend/app/domain/item.py` (see
`#/components/schemas/Item` in `openapi.json`).

Key item fields bots can rely on:

| Field | Type | Notes |
|---|---|---|
| `id` | string | Stable per-character item ID |
| `name` | string? | Unique/rare name, omitted for magic/normal |
| `typeLine` | string | Base type, always present |
| `rarity` | enum | `normal`, `magic`, `rare`, `unique`, `currency` |
| `ilvl` | int | Item level |
| `requirements` | object[] | `{name, value}` |
| `properties` | object[] | `{name, values}` |
| `explicitMods` | string[] | Human-readable lines |
| `implicitMods` | string[] | |
| `craftedMods` | string[] | |
| `enchantMods` | string[] | |
| `flavourText` | string[] | Uniques only |
| `socket` | object[]? | Planned, currently empty arrays |

### `GET /api/stashes?league=<id>`

Stash tab summary list. Read-only.

```json
{
  "league": "Dawn of the Hunt",
  "tabs": [
    {
      "id": "abc123",
      "name": "Dumper",
      "type": "NormalStash",
      "index": 0,
      "colour": {"r": 200, "g": 150, "b": 80}
    }
  ]
}
```

### `GET /api/stashes/{tab_id}?league=<id>`

Tab contents with normalized items (same `Item` schema as characters).

```json
{
  "tab": { "id": "abc123", "name": "Dumper", "type": "NormalStash", "index": 0 },
  "items": [ /* Item[] */ ]
}
```

### `POST /api/pricing/lookup`

Bulk price estimate. Input is a list of **normalized item keys** or raw items
(the backend will derive the key server-side). Response maps request keys to
`PriceEstimate`.

```json
{
  "items": [
    {"name": "Mirror of Kalandra", "base_type": "Mirror of Kalandra", "rarity": "currency"},
    {"name": "Headhunter", "base_type": "Leather Belt", "rarity": "unique"}
  ]
}
```

```json
{
  "results": [
    {"key": "currency:Mirror of Kalandra",
     "estimate": {"value": 400000, "unit": "chaos", "source": "poe_ninja", "updated_at": "2026-04-19T10:00:00Z"}},
    {"key": "unique:Headhunter",
     "estimate": {"value": 80, "unit": "chaos", "source": "poe_ninja", "updated_at": "2026-04-19T10:00:00Z"}}
  ]
}
```

Cache TTL is 15 minutes; bots should respect `Cache-Control: max-age`.

## Rate limits

Bot tokens (when introduced) are rate-limited at the edge to **60 req/min per
token** for read endpoints. `/api/pricing/lookup` is capped at **30 req/min per
token** with a soft burst of 5. Exceeding a limit returns `429` with
`Retry-After` in seconds.

The backend additionally enforces a **60-second manual refresh cooldown per
account**; since bots cannot trigger refreshes, this is informational.

## Error shape

All errors follow FastAPI's `HTTPException` default:

```json
{ "detail": "human-readable reason" }
```

Relevant status codes:

| Code | Meaning |
|---|---|
| `400` | Malformed request body / missing parameter |
| `401` | Missing or invalid session / token |
| `403` | CSRF failure or bot token lacks scope |
| `404` | Unknown character/tab for this account |
| `429` | Rate limit hit (`Retry-After` header present) |
| `503` | Upstream GGG API unhealthy (callers should retry) |

## Operational hooks

- **Admin observability** lives at `admin.<domain>` and is not part of the bot
  contract. It is documented in `admin/README.md`.
- **Metrics & tracing**: structured JSON logs include `request_id` which is
  echoed back in the `X-Request-Id` response header. Bots should log the header
  to correlate support requests.

## Change log

| Version | Change |
|---|---|
| `0.1.0` | Initial frozen contract (M6) |
