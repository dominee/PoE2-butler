# GGG API & OAuth2 Integration

Reference for integrating **PoE2 Hideout Butler** with the official GGG (Grinding Gear Games) account & game data API.

> The GGG API requires a manually approved OAuth2 client application. Approval is not instant; plan for weeks of lead time. Until approval is granted, development uses the `mock-ggg/` service which exposes the same surface area against fixture data.


## 1. Applying for a client

Send an application to **developer@grindinggear.com** with:

- Application name, URL, and short description (the "PoE2 Hideout Butler" value proposition).
- Contact email and developer identity.
- Requested scopes (see below).
- Registered redirect URIs:
  - Production: `https://api.hideoutbutler.com/api/auth/callback`
  - Staging: `https://dev-api.hideoutbutler.com/api/auth/callback`
  - Local: `http://api.localhost/api/auth/callback`
- Expected request volume and rate-limit strategy.

On approval you will receive:

- `client_id`
- `client_secret` (store only in backend env, never in the SPA bundle).
- Confirmed allowed redirect URIs (must match exactly at runtime).

Store these in the backend `.env` as:

```env
GGG_CLIENT_ID=...
GGG_CLIENT_SECRET=...
GGG_OAUTH_BASE_URL=https://www.pathofexile.com
GGG_API_BASE_URL=https://api.pathofexile.com
GGG_REDIRECT_URI=https://api.hideoutbutler.com/api/auth/callback
```

## 1b. Recommended registration inputs (hideoutbutler.com)

Use these when emailing **developer@grindinggear.com** or filling an application form.

| Field | Recommended value |
|---|---|
| **Application name** | PoE2 Hideout Butler |
| **Application URL** | `https://app.hideoutbutler.com` |
| **Short description** | Read-only PoE2 companion: users sign in with GGG OAuth2 to browse characters, equipped gear, and stash tabs online, with item insights, price estimates, and trade-site links. Does not mutate account or game state. |
| **Requested scopes** | `account:profile account:characters account:stashes account:leagues` (read-only; no write scopes) |
| **Redirect URIs** | `https://api.hideoutbutler.com/api/auth/callback`, `https://dev-api.hideoutbutler.com/api/auth/callback`, `http://api.localhost/api/auth/callback` |
| **Contact** | Your stable email (ideally on the same domain, e.g. `ops@hideoutbutler.com`) plus name / GitHub org. |
| **Expected volume** | Low-volume beta initially; login plus on-demand snapshot refresh; conservative throttling and backoff on 429. |
| **Rate-limit strategy** | Parse `X-Rate-Limit-*` headers, Redis token-bucket per account, honour `Retry-After`, exponential backoff on repeated 429s, 60 s per-user refresh cooldown. |
| **Security** | Authorization Code + PKCE + `state`; tokens server-side only, encrypted at rest; strict redirect URI match; session cookie is `HttpOnly` / `Secure` (prod) / `SameSite=Lax`. |

**Email subject (example):** `OAuth2 client registration — PoE2 Hideout Butler (hideoutbutler.com)`

## 2. Required scopes

| Scope | Used for |
|---|---|
| `account:profile` | Identify the user (GGG account name is our primary key). |
| `account:characters` | List characters and their equipped items. |
| `account:stashes` | List and read stash tabs (includes currency/special tabs). |
| `account:leagues` | Enumerate leagues the user participates in. |

Ask for the minimum set only; do **not** request any write scopes. The app never mutates GGG-side state.

## 3. OAuth2 flow

We implement the Authorization Code flow with PKCE:

```
User clicks "Sign in with GGG"
  -> GET /api/auth/login
     (server generates code_verifier + code_challenge, state; stores (state -> verifier) in Redis, 5 min TTL)
  -> 302 to GGG authorize URL with:
        response_type=code
        client_id=GGG_CLIENT_ID
        redirect_uri=GGG_REDIRECT_URI
        scope=account:profile account:characters account:stashes account:leagues
        state=<random>
        code_challenge=<S256(verifier)>
        code_challenge_method=S256
User approves on GGG
  -> GGG redirects to GGG_REDIRECT_URI with ?code=...&state=...
  -> GET /api/auth/callback:
        verify state matches stored one (and retrieve verifier)
        POST to GGG token endpoint with code + code_verifier + client_id + client_secret
        receive access_token, refresh_token, expires_in
        fetch profile -> upsert users row
        encrypt tokens (AES-GCM) and persist in user_tokens
        create Redis session (random 256-bit id -> user_id), 14 day sliding TTL
        Set-Cookie: session=<id>; HttpOnly; Secure; SameSite=Lax; Path=/
        redirect to SPA /app
```

### Token storage

- Tokens are encrypted at rest via AES-GCM with a key from `APP_SECRET_KEY` (32 bytes, base64). Key rotation is documented in `DEPLOY.md`.
- Refresh token is used server-side to obtain new access tokens automatically before calls.
- Logout clears the Redis session and best-effort revokes the refresh token at GGG.

### State & PKCE

- `state` is a 128-bit random token bound to the pending auth attempt and validated on callback.
- `code_verifier` is 64 bytes of randomness; challenge is `BASE64URL(SHA256(verifier))`.

## 4. API endpoints we consume

All calls are authenticated with `Authorization: Bearer <access_token>` and use our rate-limit-aware `httpx` client.

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/profile` | Current account profile (name, UUID). |
| `GET` | `/account/leagues` | Leagues the account has played in, with active flags. |
| `GET` | `/account/characters` | List of characters with league, class, level. |
| `GET` | `/account/characters/{name}` | Full character data incl. equipped items and inventory. |
| `GET` | `/account/stashes/{league}` | List of stash tabs for a league. |
| `GET` | `/account/stashes/{league}/{tab_id}` | Contents of a stash tab. |

> Exact paths will be confirmed from GGG documentation once credentials are issued; constants live in `backend/app/clients/ggg_client.py` and the mock mirrors them.

## 5. Rate limiting

GGG returns rate-limit telemetry via `X-Rate-Limit-*` headers and uses HTTP 429 when exceeded. Our client:

1. Parses all `X-Rate-Limit-*` and `X-Rate-Limit-*-State` headers on every response.
2. Maintains a Redis token-bucket keyed by `ggg:rl:<policy>:<account>` to pre-emptively throttle.
3. On 429, honours `Retry-After`; on repeated 429, backs off exponentially and surfaces a user-visible error.
4. Per-user `POST /api/refresh` is additionally rate-limited by a 60 s cooldown, enforced with `SET NX EX 60` in Redis.

## 6. Local development with the mock

The `mock-ggg/` service exposes:

- `/oauth/authorize` — renders a tiny HTML form where the developer picks a fixture user and confirms.
- `/oauth/token` — exchanges the code for a fake access/refresh token pair.
- `/oauth/revoke`
- `/profile`, `/account/leagues`, `/account/characters`, `/account/characters/{name}`, `/account/stashes/{league}`, `/account/stashes/{league}/{tab_id}`

Fixture data lives in `mock-ggg/app/fixtures/` as JSON. Toggle between real GGG and mock by setting `GGG_OAUTH_BASE_URL` and `GGG_API_BASE_URL` to the mock host.

## 7. Security notes

- Never log `access_token`, `refresh_token`, `code`, or `code_verifier`.
- Never return tokens to the SPA; all GGG calls stay server-side.
- Redirect URI check is strict string equality; do not use wildcards.
- The callback endpoint must reject responses where `state` or `code` is missing or has been consumed already.
