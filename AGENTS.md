# AGENTS.md — PoE2 Hideout Butler

AI-agent context file. Read this first when starting any coding session.

---

## 1. Project overview

**PoE2 Hideout Butler** is a multi-user SPA that lets Path of Exile 2 players view their characters' gear and stash contents online. It enriches item information with pricing, tier/roll quality data, and trade-site deep-links.

**Production domain:** apex **`hideoutbutler.com`**. Public services: `app.hideoutbutler.com` (SPA), `api.hideoutbutler.com` (API), `admin.hideoutbutler.com` (admin). **Cloudflare** typically fronts the origin (public TLS at the edge); the VM serves **HTTPS to Cloudflare** using a [Cloudflare Origin CA](https://developers.cloudflare.com/ssl/origin-configuration/origin-ca/) certificate (not Let’s Encrypt in this repo). Staging / optional OAuth host: `dev-api.hideoutbutler.com` (GGG registration).

**Development:** Traefik + docker-compose use **`*.dev.hideoutbutler.com`** hostnames (resolve to `127.0.0.1`); the mock GGG service is reached in the browser at `ggg.dev.hideoutbutler.com`. See **§4**.

Key features:
- GGG OAuth2 login (Authorization Code + PKCE).
- Snapshot of characters, gear, and stash tabs stored in Postgres.
- Item detail pane: rarity-coloured border, tag-stripped property names, explicit mod tiers, roll quality bars, socketed-item (rune/soul-core) display.
- Activity log: diff of current vs previous snapshot; new (green) / changed (amber) indicators in grid and table views.
- Price estimates via poe.ninja (cached in Redis).
- Admin observability app (separate FastAPI + Jinja2 on port **8001**, username + bcrypt + optional TOTP + IP allowlist).

Mandatory legal copy (GGG requirement):
- Display this exact sentence in a visible place (web footer + docs): **"This product isn't affiliated with or endorsed by Grinding Gear Games in any way."**
- GGG API requests must send an identifiable User-Agent prefixed as: **`User-Agent: OAuth {$clientId}/{$version} (contact: {$contact}) ...`** using contact **`dev@hell.sk`**.

### 1.1 GGG API: OAuth2 grant status (2026-06)

GGG has granted OAuth2 access for the application. Approved scopes:

| Scope | Status |
|---|---|
| `account:profile` | ✅ Granted — live in UAT and prod |
| `account:characters` | ✅ Granted — live in UAT and prod |
| `account:stashes` | ⏳ PoE1 only; no PoE2 stash scope available yet — blocked on GGG upstream |
| `account:leagues` | ⏳ Not yet granted — backend infers preferred league from character data |

**Stash:** `account:stashes` and related scopes apply to **Path of Exile 1** only. Per the [GGG API reference](https://www.pathofexile.com/developer/docs/reference#stashes), no PoE2 stash scope exists yet. PoE2 stash browsing still uses `mock-ggg/` in the dev stack. The app is implemented to work when GGG provides a PoE2 scope; treat stash integration as **blocked on upstream**.

**Leagues:** `account:leagues` was not granted. `GET /account/leagues` is **not** called. `snapshot.py → refresh_user_snapshot` falls back to `pick_league_from_characters` (in `domain/league.py`), which extracts the most common non-permanent league from the character list and sets `user.preferred_league`.

**Environments:**
- **Dev** (`docker-compose.dev.yml`): uses `mock-ggg/`; GGG_CLIENT_ID/SECRET are placeholders.
- **UAT** (`docker-compose.uat.yml`): uses **live GGG** credentials; **no mock-ggg service**. DNS `*.uat.hideoutbutler.com → 127.0.0.1` required locally. See `GGG_API.md` §6.1.
- **Prod**: same as UAT configuration with production redirect URI.

**`GGG_SCOPES` must only contain granted scopes.** Requesting `account:stashes` or `account:leagues` will cause GGG to reject the entire authorization flow.

### 1.2 Product extensions and delivery policy (INSTRUCTIONS §Product extensions)

Authoritative detail: [INSTRUCTIONS.md](INSTRUCTIONS.md) section **“Product extensions (Phase 2+) — analysis and acceptance”**. Locked decisions for implementers:

- **TDD:** New features follow test-first: derive cases from `INSTRUCTIONS.md`, then implement until tests pass (see INSTRUCTIONS §Implementation approach).
- **Clipboard text:** PoE2-style block strings; goldens in `mock-ggg/samples/*.txt`; [`backend/app/domain/item_text.py`](backend/app/domain/item_text.py); optional `item_class` / `flavour_text` / `trailer_note` on `Item` in [`backend/app/domain/item.py`](backend/app/domain/item.py).
- **Public share links:** `share_id` UUID, **world-readable**; warn in UI; revoke + rate limit on create. `POST/DELETE /api/shares` (CSRF), `GET /api/public/items/{id}`; model `ItemShare` in [`backend/app/db/models.py`](backend/app/db/models.py); limiter in [`backend/app/services/share_ratelimit.py`](backend/app/services/share_ratelimit.py).
- **Image export:** Client-side PNG (two layouts) in [`frontend/src/features/items/ItemImageExport.tsx`](frontend/src/features/items/ItemImageExport.tsx) (`html-to-image`); no mandatory server render on small VM.
- **Stat summary:** [`backend/app/domain/stat_summary.py`](backend/app/domain/stat_summary.py) (heuristic MVP); expand data files later.
- **Queue:** **Redis + arq** for background work; per–API throttling in [`backend/app/services/third_party_ratelimit.py`](backend/app/services/third_party_ratelimit.py); job `refresh_trade_filter_catalog` in worker. No RabbitMQ unless requirements outgrow this.
- **Pricing (hybrid):** Aggregators (e.g. poe.ninja) for bulk/cache + optional community APIs; for detail-pane “refined” numbers, the **public** GGG PoE2 **trade JSON** API: **POST** search returns the first page of listing ids in **`result`**; **`GET …/fetch`** loads listing JSON for median chaos (optional **GET …/search** paging when the API includes a `result` array). Not browser HTML scraping. Label as indicative / snapshot. **All** server-side trade2 calls (worker + `POST /api/trade/search`) share a **global Redis lock** (`tp3:ggg_trade:lock` in `third_party_ratelimit.py`): wait before each call, extend TTL after HTTP 200 (min interval + extra spacing), and on **429** parse `Please wait N seconds` (plus buffer, capped). Env: `GGG_TRADE_*` in `deploy/env/.env.example`. See [docs/pricing_estimates.md](docs/pricing_estimates.md) and [docs/trade_deeplinks.md](docs/trade_deeplinks.md). The item detail pane only **enqueues** a refined estimate after an explicit user action (refresh), not automatically on open/login.
- **Admin console:** Overview shows arq job breakdown, Redis **throttle** key PTTLs (including `ggg_trade2_lock`), price-job samples with **Updated** (UTC) from last `save_job_state`, and optional **manual** or **user-started** live refresh to `/admin/api/summary` (no auto-poll on login when live refresh is enabled). See [admin/README.md](admin/README.md).
- **Trade filters:** [`backend/app/services/trade_stat_catalog.py`](backend/app/services/trade_stat_catalog.py) (bundled template→stat hash map) + [`backend/app/services/trade_url.py`](backend/app/services/trade_url.py); deep link POST in [`backend/app/services/trade_search_submit.py`](backend/app/services/trade_search_submit.py); see [docs/trade_deeplinks.md](docs/trade_deeplinks.md). Three search modes: `exact` (tolerance-based min/max per stat), `upgrade` (min-floor at 95% of current roll per stat), `weighted_upgrade` (top stats weighted by current tier — T1=30, T2=20, T3=15, T4+=10 — floor = `⌊Σ(baseline × weight) × 0.85⌋`). **GGG anonymous API restriction:** the `weight` stat-group type exceeds GGG's server-side complexity budget for unauthenticated callers; when GGG returns HTTP 400, the backend automatically retries as a regular `upgrade` search so the user always receives a valid trade URL. See Known gotchas § *GGG weight group*.

---

## 2. Repository layout

```text
PoE2-butler/
├── backend/          Python 3.12 · FastAPI · SQLAlchemy 2 · arq · uv
│   ├── app/
│   │   ├── api/      Route handlers (auth, characters, stashes, activity, pricing, trade, prefs)
│   │   ├── clients/  GGG httpx client
│   │   ├── config.py pydantic-settings (all env vars)
│   │   ├── db/       SQLAlchemy models + session factory
│   │   ├── domain/   Item parsing, trade-query builders
│   │   ├── services/ Snapshot service, pricing service
│   │   └── workers/  arq worker (snapshot refresh + price warming)
│   └── alembic/      Migrations (0001_init → 0003_prev_payload)
├── frontend/         React 18 · Vite · TypeScript · TanStack Query · Zustand · Tailwind
│   └── src/
│       ├── api/      hooks.ts · types.ts · client.ts
│       ├── features/ activity · characters · items · stashes · app
│       ├── store/    uiStore (Zustand)
│       └── utils/    modText.ts (stripTags, parseModParts)
├── admin/            FastAPI + Jinja2 (port 8001); not bundled in the SPA
├── mock-ggg/         Dev mock of GGG OAuth2 + API (FastAPI, port 9000)
│   ├── app/fixtures/ users.json · characters.json · stashes.json
│   └── samples/      poe.ninja character exports + convert.py
├── deploy/
│   ├── compose/      docker-compose.{dev,uat,prod}.yml
│   │   └── traefik/  traefik.{dev,uat,prod}.yml · dynamic.{dev,uat,prod}.yml · certs/ (PEM+key, UAT+prod)
│   └── env/          .env.example · .env.uat.example · .env.* (gitignored)
├── docs/
├── INSTRUCTIONS.md   Original / product requirements (optional; may be local-only)
├── AGENTS.md         This file
├── DEPLOY.md         Build & deploy runbook (incl. Cloudflare + origin certs)
├── GGG_API.md        GGG OAuth2 integration
└── SECURITY.md       Security checklist
```

---

## 3. Architecture

```text
Browser
  ├─ React SPA     (app.dev… · prod: app.hideoutbutler.com)
  │     └ /api/*    proxied in dev to backend (Vite) · prod: same-origin via app host or direct API
  ├─ Admin console (admin.dev… / admin.hideoutbutler.com)  FastAPI + Jinja2, /admin/…; GET / → 302 /admin/
  └─ (OAuth)       GGG or mock-ggg — browser authorize URL is env-specific (see §4, §7)
        │
        ▼
  FastAPI backend  (api.dev… · prod: api.hideoutbutler.com)
        ├─ PostgreSQL 16
        ├─ Redis 7
        └─ GGG API or mock-ggg (server-to-server; Docker service name mock-ggg in dev)
```

- **Traefik v3** routes in dev and prod (see **§4** for TLS and providers).
- **arq** worker runs in the same Docker image as the backend: `arq app.workers.arq_worker.WorkerSettings`.
- GGG API calls are **server-side only**; tokens never reach the browser.

---

## 4. Environments: Traefik, hosts, and TLS

### 4.1 Local development (`docker-compose.dev.yml`)

| Topic | Details |
|-------|--------|
| **Routing** | `deploy/compose/traefik/traefik.dev.yml` + **`dynamic.dev.yml`** (file provider **only** — no Docker socket mounted in Traefik in dev). |
| **Hostnames** | `app`, `api`, `admin`, `ggg` as **`app.dev.hideoutbutler.com`**, etc. Point to `127.0.0.1` (wildcard DNS or `/etc/hosts`). |
| **Env** | `deploy/env/.env.dev` from `.env.example`: `APP_BASE_URL`, `API_BASE_URL`, `CORS_ALLOW_ORIGINS`, `GGG_OAUTH_AUTHORIZE_BASE_URL` (e.g. `http://ggg.dev.hideoutbutler.com`), and internal `GGG_*` to `mock-ggg` (compose wires server-side URLs). |
| **Vite** | `frontend/vite.config.ts`: `server.allowedHosts` must include the SPA dev hostname; optional extra hosts via `VITE_ALLOWED_HOSTS` (comma-separated). |
| **GGG redirect (dev)** | `GGG_REDIRECT_URI` uses the **app** host, e.g. `http://app.dev.hideoutbutler.com/api/auth/callback`, so the browser follows OAuth back to the SPA origin; **Vite proxies** `/api/*` to the backend and session cookies stay same-site. |
| **Mock GGG** | Browser → `http://ggg.dev.hideoutbutler.com`; containers use `http://mock-ggg:9000`. |
| **Admin** | `http://admin.dev.hideoutbutler.com` — Jinja summary dicts use **`key_count`**, not a key named `keys` (which breaks as `{{ dict.keys }}` in Jinja). |

### 4.2 Production (`docker-compose.prod.yml`)

| Topic | Details |
|-------|--------|
| **Routing** | Traefik uses the **Docker provider** (socket mounted) + static **`dynamic.prod.yml`** (TLS default cert only; **no** `http.routers` in the file). |
| **App + `/api`** | Same pattern as UAT: the backend service defines router **`app-api`**: `Host(APP_DOMAIN) && PathPrefix(/api)` with **priority 100**; the **frontend** `app` router has **priority 1** so `https://app…/api/...` hits FastAPI and `https://app…/` hits the static SPA. Router **`api`** still exposes **`API_DOMAIN`** to the same backend. |
| **Host ports** | Traefik must publish **`80:80` and `443:443`**. `docker ps` without **`443->443`** usually means the **dev** stack (which maps `8080` for the dashboard) or an outdated prod compose. Cloudflare **Full (strict)** needs TLS on the origin. |
| **TLS** | **No ACME in-repo.** `dynamic.prod.yml` sets the default TLS store to PEM + key at **`/certs/cloudflare-origin.pem`** and **`/certs/cloudflare-origin.key`**; host path **`deploy/compose/traefik/certs/`** is mounted read-only. Create certs in **Cloudflare → SSL/TLS → Origin Server**. **Docker** routers set **`traefik…tls=true`** (file-based `tls: {}` is not used for these routes). |
| **Cloudflare** | **Proxied** A records, SSL mode **Full (strict)**. See `DEPLOY.md` §4.3. |
| **GGG redirect (prod)** | For **session cookies** + relative `/api` on the app host, register and set **`GGG_REDIRECT_URI=https://app.hideoutbutler.com/api/auth/callback`** (see `GGG_API.md`). The **API** hostname alone is still useful for `API_DOMAIN` and tooling. |
| **Env** | Optional `SECURITY_CONTACT_EMAIL` for ops / disclosure text (not consumed by Traefik). |

### 4.3 UAT (`docker-compose.uat.yml`)

| Topic | Details |
|-------|--------|
| **Purpose** | Public acceptance testing against **live GGG OAuth2** with **HTTPS** to the origin (Cloudflare Origin CA), same cookie/`/api` pattern as prod. |
| **Project** | Compose name **`poe2b-uat`**, networks **`poe2b_uat_*`**, containers **`poe2b-uat-*`** — can run beside dev/prod on one host. |
| **GGG** | **No `mock-ggg` service.** Real `GGG_CLIENT_ID` / `GGG_CLIENT_SECRET`; `GGG_API_REALM=poe2`; `GGG_SCOPES=account:profile account:characters` only. |
| **Routing** | **File provider only** (`traefik.uat.yml` + **`dynamic.uat.yml`**) — no Docker socket. Each router on **`websecure` must set `tls: {}`**. |
| **App host** | Traefik matches **`PathPrefix(/api)`** → backend, else → static **`frontend`**. Set `APP_BASE_URL`, `CORS`, and `GGG_REDIRECT_URI` to the **exact** browser origin (`https://app.uat…`). |
| **Other hosts** | `admin.uat…` (+ prod admin pair if configured); no `ggg.uat` host (browser OAuth goes to GGG). |
| **TLS / CF** | Same `deploy/compose/traefik/certs/cloudflare-origin.{pem,key}` paths as prod; add **`*.uat.hideoutbutler.com`** (or each FQDN) to the Origin certificate. |
| **Worker** | `arq` worker service included. |
| **Env** | `deploy/env/.env.uat` (copy from **`.env.uat.example`**) and `ENVIRONMENT=uat` (enables `Secure` cookies in backend, like prod). |

`DEPLOY.md` §4.6 and `GGG_API.md` §6.1 have the full runbook.

---

## 5. Key technical conventions

### Backend

| Concern | Approach |
|---|---|
| Virtual env | `uv` — use `uv sync` / `uv run` |
| Settings | `pydantic-settings`; class `Settings` in `backend/app/config.py` |
| DB session | `get_db()` async generator → yields `AsyncSession` |
| ORM | SQLAlchemy 2 async (`AsyncSession`); Alembic migrations |
| Token encryption | AES-GCM, key from `APP_SECRET_KEY` |
| Sessions | Redis session ID in signed `httpOnly SameSite=Lax` cookie `poe2b_session` |
| CSRF | Double-submit cookie pattern |
| Logging | `structlog` structured JSON; `request_id` middleware |
| Tests | `pytest` + `pytest-asyncio`; fixtures in `tests/conftest.py` |
| Lint | `ruff` (format + lint); run via `uv run ruff check .` |

**Mod tier database** (`backend/app/data/mod_ranges.json`):

The file is committed to the repository and baked into the Docker image at build time. It has three top-level sections:

| Section | Contents |
|---|---|
| `stat_hashes` | GGG magnitude `hash` → `{ name, tier, min, max }` (populated by `extract_mod_ranges.py` from sample data) |
| `mod_names` | GGG display mod `name` → `{ group, tiers: [{tier, required_level, min, max}] }` (populated by `ingest_repoe_mods.py`) |
| `mod_groups` | RePoE mod family `group` → sorted list of all tier dicts, T1-first (populated by `ingest_repoe_mods.py`) |

**Re-import trigger:** run `ingest_repoe_mods.py` after each PoE2 game patch (~quarterly) or whenever new mod tiers appear. Commit the result and redeploy — the build picks it up automatically. See `DEPLOY.md` §2.4 for the full procedure.

```bash
# Full re-import from RePoE — all player-relevant domains (item, crafted, flask, …)
uv run python backend/scripts/ingest_repoe_mods.py

# Restrict to domain=item only (faster, for testing)
uv run python backend/scripts/ingest_repoe_mods.py --limited

# Explicit domain list
uv run python backend/scripts/ingest_repoe_mods.py --domains item crafted

# Optional: update stat_hashes from poe.ninja samples (default samples dir)
uv run python backend/scripts/extract_mod_ranges.py

# Extra sample directories for broader hash coverage
uv run python backend/scripts/extract_mod_ranges.py --samples mock-ggg/samples /path/to/more

# Quick smoke-test with only the first 3 sample files
uv run python backend/scripts/extract_mod_ranges.py --limited 3
```

**Snapshot model** (`backend/app/db/models.py`):

```python
class Snapshot(Base):
    payload: Mapped[dict]           # current GGG data
    prev_payload: Mapped[dict|None]  # previous snapshot (for activity diff)
```

`upsert_snapshot` in `backend/app/services/snapshot.py` shifts `payload → prev_payload` on update; **first insert** also stores a baseline copy in `prev_payload` so `GET /api/activity` can report `has_prev` immediately. OAuth callback runs `refresh_stashes` after leagues resolve `preferred_league` so stash tabs exist before the first manual refresh.

**Item parsing** (`backend/app/domain/item.py`):

- `_strip_tags(text)` removes `[Label|Short]` or `[Plain]` GGG markdown tags.
- `ModDetail` / `ModMagnitude` capture tier + roll ranges from `item.extended.mods`.
- `socketed_items: list[Item]` recursively parsed from `item.socketedItems` (runes, soul cores).
- **Bundled unique extras:** `backend/app/data/unique_reference.json` supplies missing **flavour** and **per-mod “type” roll** hints (wiki-style) for specific `name` + `baseType`; `unique_reference.py` + `parse_item` map those to `implicit_mod_range_hints` / `explicit_mod_range_hints`. Maintainer ingest from poe2db: see [docs/unique_reference.md](docs/unique_reference.md).

### Frontend

| Concern | Approach |
|---|---|
| State | Zustand `uiStore` (view, league, character, tab, stash layout) |
| Server state | TanStack Query; keys in `queryKeys` map in `hooks.ts` |
| Styling | Tailwind CSS with custom design tokens (ink-*, ember-*, parchment-*, rarity-*) |
| Mod rendering | `parseModParts` + `ModText` component for numeric highlighting |
| Tag stripping | `stripTags(text)` in `frontend/src/utils/modText.ts` |
| Roll quality | `PercentBar` component + `computeItemScore` in `features/items/PercentBar.tsx` |
| Activity | `useActivity(league)` hook; `ActivityLog` collapsible panel (left column) |

### CI / quality gates

| Concern | Approach |
|---|---|
| CI trigger | `.github/workflows/ci.yml` runs on push/PR to `main` |
| Python CI | `uv sync --frozen || uv sync`, then `ruff check` and `pytest` (backend default `addopts` excludes `live_ggg`; run `pytest -m live_ggg` manually against UAT) |
| Pre-push (full) | `make test-all-docker` — all services in Docker plus security scans (see [TESTS.md](TESTS.md)) |
| Frontend runtime | Node `22` |
| Frontend cache | `actions/cache` caches `~/.npm` keyed by `hashFiles('frontend/package.json')` |
| Frontend lint | `npm run lint || true` (non-blocking today) |
| Dependency audits | `pip-audit` and `npm audit` run with `|| true` (informational) |
| Pre-push expectation | Run backend + frontend tests locally before pushing (same commands as README); optional `make test-all-docker` for full parity |

### Security review workflow plan (stored context)

- Workflow file: `.github/workflows/security-review.yml`
- Phase: visibility-only (all jobs `continue-on-error: true`)
- Included checks:
  - Semgrep SAST (`--config auto`)
  - gitleaks secret scan
  - `actions/dependency-review-action` (PR only)
  - `osv-scanner` recursive scan
  - `pip-audit` (`backend`, `admin`, `mock-ggg`)
  - `npm audit` (`frontend`)
- Rollout intent:
  1. Baseline findings and tune suppressions.
  2. Promote critical checks (secrets + high/critical deps) to blocking.
  3. Later tighten SAST severities after false-positive cleanup.

**Rarity colour tokens** (Tailwind):

```text
text-rarity-normal  text-rarity-magic  text-rarity-rare  text-rarity-unique
text-rarity-currency  text-rarity-gem  text-rarity-quest
border-rarity-*  (same names)
```

---

## 6. Key data flows

### Auth / first login

1. `GET /api/auth/login` → generates PKCE, stores state in Redis, redirects to GGG authorize URL.
2. GGG → `GET /api/auth/callback?code=&state=` on the registered redirect host → exchanges code, upserts `User` + `UserToken`, triggers `refresh_user_snapshot` in a separate `snap_db` session, sets session cookie.
3. `await db.refresh(user)` ensures `preferred_league` populated before setting the session.

### Snapshot refresh

`POST /api/refresh` (optional query `league=` — defaults to `User.preferred_league` so the header league matches stash tabs and `GET /api/activity`) → `refresh_user_snapshot` → fetches profile / leagues / characters / stashes from GGG → upserts snapshots in Postgres (shifting `payload → prev_payload`). Does **not** enqueue pricing. **`POST /api/pricing/apprise`** queues stash hybrid estimates (missing DB rows first, capped).

### Activity diff

`GET /api/activity?league=X` → loads `STASH_TAB` snapshots, compares `payload` vs `prev_payload` item-by-item (by `id`), returns `new_items`, `changed_items`, `removed_items` grouped by tab.

### Stash item display

`StashBrowser` → `useStashTab` + `usePriceLookup` + `useActivity` → passes:

- `highlightIds` (valuable items, `price ≥ threshold` → gold outline `outline-yellow-400`)
- `activityMap` (Map<itemId, "new"|"changed"> → corner dot: emerald-400 / amber-400)

---

## 7. Environment variables (key subset)

| Variable | Purpose |
|---|---|
| `APP_SECRET_KEY` | AES-GCM key for token encryption (32 bytes, base64) |
| `SESSION_SIGNING_KEY` | Cookie signing key |
| `GGG_CLIENT_ID` / `GGG_CLIENT_SECRET` | GGG OAuth2 credentials |
| `GGG_OAUTH_BASE_URL` | Internal (server-to-server) GGG or mock base URL |
| `GGG_OAUTH_AUTHORIZE_BASE_URL` | Browser authorize URL — dev: `http://ggg.dev.hideoutbutler.com`; prod: usually empty (real GGG host) |
| `GGG_REDIRECT_URI` | **Dev:** `http://app.dev…/api/auth/callback` (Vite). **UAT:** `https://app.uat…/api/auth/callback` (Traefik file routes). **Prod (recommended):** `https://app.hideoutbutler.com/api/auth/callback` so OAuth sets cookies on the **app** origin used by the SPA; requires GGG to allow that redirect URI. |
| `CORS_ALLOW_ORIGINS` | JSON array string, e.g. `["https://app.hideoutbutler.com"]` or dev equivalent |
| `PRICING_SOURCE` | `static` (dev) or `poe_ninja` |
| `DEFAULT_VALUABLE_THRESHOLD_CHAOS` | Starting threshold for valuable item highlights |
| `GGG_TRADE_MIN_INTERVAL_SEC` | Base seconds in the global trade2 lock after each **successful** GGG response (alias: `GGG_TRADE_FETCH_MIN_INTERVAL_SEC`) |
| `GGG_TRADE_EXTRA_SPACING_SEC` | Extra seconds added to that lock TTL (default 5; total ≈ min + extra) |
| `GGG_TRADE_429_BUFFER_SEC` / `GGG_TRADE_429_FALLBACK_SEC` / `GGG_TRADE_429_MAX_WAIT_SEC` | On HTTP 429: add buffer to parsed wait, fallback if unparseable, cap |
| `SECURITY_CONTACT_EMAIL` | Optional ops / security contact (e.g. disclosure; not read by app code) |
| `ADMIN_DASHBOARD_REFRESH_SEC` | `0` = no JS polling; `>0` enables **Refresh now** / **Start auto-refresh** on the Overview (operators choose when to poll) |

---

## 8. Database migrations

Migrations live in `backend/alembic/versions/`. After adding a model change:

```bash
# Generate
docker compose -f deploy/compose/docker-compose.dev.yml --env-file deploy/env/.env.dev \
  exec backend alembic revision --autogenerate -m "describe_change"

# Apply
docker compose -f deploy/compose/docker-compose.dev.yml --env-file deploy/env/.env.dev \
  exec backend alembic upgrade head
```

Current migrations:
- `0001_init` — users, user_tokens, snapshots, snapshot_kind enum
- `0002_valuable_threshold` — adds `valuable_threshold_chaos` to users
- `0003_prev_payload` — adds `prev_payload JSONB` to snapshots

---

## 9. Mock GGG service

Located in `mock-ggg/`. Stash simulation and optional extra OAuth rows live under `mock-ggg/app/fixtures/` (`static_users.json`, `characters.json`, `stashes.json`). The mock login list is driven primarily by [`mock-ggg/config/poe_ninja_characters.toml`](mock-ggg/config/poe_ninja_characters.toml) (see “Live Poe.ninja characters” below).

**Live Poe.ninja characters (dev):** URLs are listed in [`mock-ggg/config/poe_ninja_characters.toml`](mock-ggg/config/poe_ninja_characters.toml). On startup the mock calls Poe.ninja (`/poe2/api/events/character/...` then `.../model/{version}`), converts `charModel` to the same GGG-shaped JSON as the real account API, and registers one OAuth user per URL account segment (e.g. `dominee_9275`). `GET /account/characters` and `GET /account/characters/{name}` re-fetch from Poe.ninja so a backend **Refresh** (which clears cached character snapshots) pulls fresh gear.

Environment:

- `MOCK_GGG_POE_NINJA_TOML` — optional path to a replacement TOML (e.g. bind-mount in Compose).
- `MOCK_GGG_SKIP_POE_NINJA=1` — skip live Poe.ninja HTTP (used by backend tests); TOML-defined OAuth users still appear on the mock login form, with gear seeded from `characters.json` where names match.
- `MOCK_GGG_POE_NINJA_MIN_INTERVAL_SEC` — minimum pause **after each successful** Poe.ninja HTTP response (default `0.75`). Applies to background warm-up and on-demand `/account/characters*` fetches.
- `GET /account/characters` stays **fast** for OAuth (cached list or URL-derived placeholders). Full Poe.ninja rescrape uses `GET /account/characters?revalidate=1` (the backend passes this on **manual Refresh** only).

To regenerate fixture data from **offline** poe.ninja JSON exports:

```bash
cd mock-ggg && uv run python samples/convert.py  # reads samples/*.json, writes app/fixtures/*.json
```

The mock login form lists OAuth users in dict insertion order: optional `static_users.json` entries first, then TOML-derived accounts (e.g. `dominee_9275`).

---

## 10. Pending work (as of 2026-05-19)

| # | Task | Notes |
|---|---|---|
| 1 | Image-first icon grid view for stash | Display `item.icon` from PoE CDN with stat overlay |
| 2 | Cross-tab stash search | Query all loaded tab snapshots, not just current |
| 3 | Character items table view | Mirror stash table view for equipped gear |
| 4 | Currency stash tab renderer | Fixed-grid layout matching in-game currency tab |
| 5 | ~~Real GGG API approval~~ | **DONE** (2026-06) — `account:profile` + `account:characters` granted. `account:stashes` (PoE2) and `account:leagues` pending. |
| 6 | DigitalOcean VM provisioning | See `DEPLOY.md` |
| 7 | ~~Backend tests: update Item fixtures~~ | ~~Add `explicit_mod_details`, `socketed_items` fields~~ — **DONE** |
| 8 | ~~Frontend tests: ActivityLog, PercentBar~~ | ~~Unit tests missing~~ — **DONE** |
| 9 | `AGENTS.md` subagent skills | Create skills for domain-specific contexts if needed |
| 10 | Weighted upgrade search — GGG weight group | Falls back to min-floor upgrade when GGG rejects weight group (anonymous complexity limit). Future: pass user's GGG OAuth token in request headers so authenticated callers get the higher complexity budget. |

---

## 11. Known gotchas

- **OAuth `GGG_REDIRECT_URI`**: **Dev** uses the **app** host + Vite **/api** proxy. **Prod** and **UAT** use Traefik to send **/api** on the app host to the backend; set **`GGG_REDIRECT_URI`** to **`https://<app-host>/api/auth/callback`** so `Set-Cookie` matches the origin the SPA uses for `fetch("/api/…")` (host-only cookies). A callback only on **`api.…`** does not send cookies to **`app.…`** unless you add a shared `Domain` cookie (not implemented here).
- **Enum mapping**: `Snapshot.kind` uses `values_callable=lambda e: [m.value for m in e]` + `create_type=False` to avoid `snapshot_kind` type conflicts across Alembic runs.
- **Transaction isolation**: `refresh_user_snapshot` runs in a separate `snap_db` session committed before the main auth session is committed — prevents `InFailedSQLTransactionError` on snapshot write errors.
- **CORS**: `CORS_ALLOW_ORIGINS` must be a JSON array string, e.g. `["http://app.dev.hideoutbutler.com"]`.
- **Bcrypt hashes in env files**: `$` must be escaped as `$$` in docker-compose `--env-file` files.
- **Traefik dev / UAT**: only the **file** provider for routes (`dynamic.dev.yml` / `dynamic.uat.yml`) — no Docker socket. **UAT** also loads TLS + HTTPS routes from the same `dynamic.uat.yml`. **Prod** Traefik uses the **Docker** provider for routing and **`dynamic.prod.yml` + `certs/`** (Cloudflare Origin CA) for TLS, not Let’s Encrypt. **Prod requires Traefik v3.6.1+** (repo pins v3.7.1): Docker Engine 29+ rejects the Docker API client in Traefik v3.1 (`client version 1.24 is too old`). UAT is unaffected because it does not mount the Docker socket.
- **Admin templates**: for dicts passed to Jinja, avoid a key named `keys` (use e.g. `key_count`); `{{ d.keys }}` prints the method object, not a count.
- **Frontend unit test scope**: `npm test` runs Vitest unit tests and excludes `frontend/e2e/**`; run Playwright via `npm run test:e2e`.
- **Frontend CI cache key**: `actions/cache` uses `frontend/package.json` (no root lockfile in repo for npm).
- **UAT → PROD parity rule**: any bug found in UAT must be verified against production config/code paths too. Fixes should either (a) apply to both environments, or (b) be intentionally environment-scoped with an explicit note explaining why prod is unaffected.
- **GGG weight group (trade2)**: GGG's server-side trade2 API rejects `weight`-type stat groups from unauthenticated (non-browser-session) callers with HTTP 400 "Query is too complex". The `weight` group has a high base complexity that exceeds the anonymous budget regardless of filter count — `and` groups with 6 filters (complexity 14) succeed while `weight` groups with even 3 filters fail. `submit_trade_search` now returns a 4-tuple `(search_id, data, rate_limited, status_code)`; callers check `status_code == 400` to distinguish this from other errors. The `weighted_upgrade` handler in `trade.py` automatically retries as a regular `upgrade` search on 400. Future fix: attach the user's GGG OAuth access token to the request — authenticated users get a higher complexity limit on the GGG trade site ("Logging in will increase this limit").

---

## Document map

| File | Use |
|------|-----|
| `CHANGELOG.md` | User-facing behavior and UI changes by date |
| `README.md` | Human quick start, feature list, links |
| `DEPLOY.md` | VM setup, Cloudflare, origin PEM/key paths, compose commands, mod tier DB re-import (§2.4) |
| `GGG_API.md` | GGG OAuth registration, redirect URIs, flows, UAT live-GGG runbook (§6.1), `verify_ggg_oauth.py`, `live_ggg` tests |
| `docs/pricing_estimates.md` | Hybrid tier A/B/C, POST `result` ids + fetch, GGG lock + 429, async jobs, `GGG_TRADE_*` / `TRADE_LISTING_*` |
| `docs/trade_deeplinks.md` | Trade2 POST (ids in body), optional GET paging, fetch URL, User-Agent, server-side throttling pointer |
| `docs/unique_reference.md` | Unique-item extra data (flavour text, per-mod type hints); maintainer ingest from poe2db |
| `admin/README.md` | Admin routes, dashboard refresh controls, throttle / job tables |
| `TESTS.md` | Local and Docker test commands; `live_ggg` marker; `make test-all-docker` |
| `backend/scripts/ingest_repoe_mods.py` | Re-imports mod tier data from RePoE into `mod_ranges.json`; run after game patches |
| `backend/scripts/extract_mod_ranges.py` | Populates `stat_hashes` section from poe.ninja character samples; run after adding new samples |
