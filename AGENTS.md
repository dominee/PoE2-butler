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
│   ├── compose/      docker-compose.dev.yml · docker-compose.prod.yml
│   │   └── traefik/  traefik.{dev,prod}.yml · dynamic.{dev,prod}.yml · certs/ (PEM+key, prod)
│   └── env/          .env.example · .env.dev / .env.prod (gitignored)
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
| **Routing** | Traefik uses the **Docker provider** (socket mounted) + static **`dynamic.prod.yml`**. |
| **TLS** | **No ACME in-repo.** `dynamic.prod.yml` sets the default TLS store to PEM + key at **`/certs/cloudflare-origin.pem`** and **`/certs/cloudflare-origin.key`**; host path **`deploy/compose/traefik/certs/`** is mounted read-only. Create certs in **Cloudflare → SSL/TLS → Origin Server**. |
| **Cloudflare** | **Proxied** A records, SSL mode **Full (strict)**. See `DEPLOY.md` §4.3. |
| **GGG redirect (prod)** | **Registered** callback is on the **API** host: `https://api.hideoutbutler.com/api/auth/callback` (see `GGG_API.md` / `deploy/env/.env.example`). This differs from dev, where the app host is used for same-origin + Vite proxy. |
| **Env** | Optional `SECURITY_CONTACT_EMAIL` for ops / disclosure text (not consumed by Traefik). |

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

**Snapshot model** (`backend/app/db/models.py`):

```python
class Snapshot(Base):
    payload: Mapped[dict]           # current GGG data
    prev_payload: Mapped[dict|None]  # previous snapshot (for activity diff)
```

`upsert_snapshot` in `backend/app/services/snapshot.py` shifts `payload → prev_payload` before writing the new data.

**Item parsing** (`backend/app/domain/item.py`):

- `_strip_tags(text)` removes `[Label|Short]` or `[Plain]` GGG markdown tags.
- `ModDetail` / `ModMagnitude` capture tier + roll ranges from `item.extended.mods`.
- `socketed_items: list[Item]` recursively parsed from `item.socketedItems` (runes, soul cores).

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
| Python CI | `uv sync --frozen || uv sync`, then `ruff check` and `pytest` |
| Frontend runtime | Node `22` |
| Frontend cache | `actions/cache` caches `~/.npm` keyed by `hashFiles('frontend/package.json')` |
| Frontend lint | `npm run lint || true` (non-blocking today) |
| Dependency audits | `pip-audit` and `npm audit` run with `|| true` (informational) |
| Pre-push expectation | Run backend + frontend tests locally before pushing (same commands as README) |

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

`POST /api/refresh` → `refresh_user_snapshot(user_id, db)` → fetches profile / leagues / characters / stashes from GGG API → upserts snapshots in Postgres (shifting `payload → prev_payload`).

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
| `GGG_REDIRECT_URI` | **Dev (typical):** `http://app.dev.hideoutbutler.com/api/auth/callback` (Vite proxy). **Prod (registered with GGG):** `https://api.hideoutbutler.com/api/auth/callback` |
| `CORS_ALLOW_ORIGINS` | JSON array string, e.g. `["https://app.hideoutbutler.com"]` or dev equivalent |
| `PRICING_SOURCE` | `static` (dev) or `poe_ninja` |
| `DEFAULT_VALUABLE_THRESHOLD_CHAOS` | Starting threshold for valuable item highlights |
| `SECURITY_CONTACT_EMAIL` | Optional ops / security contact (e.g. disclosure; not read by app code) |

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

Located in `mock-ggg/`. Fixture data in `mock-ggg/app/fixtures/`.

To regenerate fixture data from poe.ninja exports:

```bash
cd mock-ggg/samples
python convert.py  # reads *.json, writes ../app/fixtures/characters.json
```

The first entry in `users.json` is auto-selected on the mock login form.

---

## 10. Pending work (as of 2026-04-19)

| # | Task | Notes |
|---|---|---|
| 1 | Image-first icon grid view for stash | Display `item.icon` from PoE CDN with stat overlay |
| 2 | T1 mod database (bundled JSON) | Needed to complete roll % bar — compare vs T1 range |
| 3 | Cross-tab stash search | Query all loaded tab snapshots, not just current |
| 4 | Character items table view | Mirror stash table view for equipped gear |
| 5 | Currency stash tab renderer | Fixed-grid layout matching in-game currency tab |
| 6 | Real GGG API approval | Apply to developer@grindinggear.com |
| 7 | DigitalOcean VM provisioning | See `DEPLOY.md` |
| 8 | Backend tests: update Item fixtures | Add `explicit_mod_details`, `socketed_items` fields |
| 9 | Frontend tests: ActivityLog, PercentBar | Unit tests missing |
| 10 | `AGENTS.md` subagent skills | Create skills for domain-specific contexts if needed |

---

## 11. Known gotchas

- **OAuth `GGG_REDIRECT_URI` (dev vs prod)**: In **dev**, use the **app** hostname so OAuth returns to the SPA; **Vite proxies** `/api/*` to the backend. In **prod**, the registered GGG callback is normally **`https://api.hideoutbutler.com/api/auth/callback`** (API host) — do not conflate the two in documentation or `GGG_API.md` examples.
- **Enum mapping**: `Snapshot.kind` uses `values_callable=lambda e: [m.value for m in e]` + `create_type=False` to avoid `snapshot_kind` type conflicts across Alembic runs.
- **Transaction isolation**: `refresh_user_snapshot` runs in a separate `snap_db` session committed before the main auth session is committed — prevents `InFailedSQLTransactionError` on snapshot write errors.
- **CORS**: `CORS_ALLOW_ORIGINS` must be a JSON array string, e.g. `["http://app.dev.hideoutbutler.com"]`.
- **Bcrypt hashes in env files**: `$` must be escaped as `$$` in docker-compose `--env-file` files.
- **Traefik dev**: only the **file** provider (`dynamic.dev.yml`) — no Docker socket in the Traefik container. Prod Traefik **does** use the Docker provider; TLS from **`dynamic.prod.yml` + `certs/`** (Cloudflare Origin CA), not Let’s Encrypt.
- **Admin templates**: for dicts passed to Jinja, avoid a key named `keys` (use e.g. `key_count`); `{{ d.keys }}` prints the method object, not a count.
- **Frontend unit test scope**: `npm test` runs Vitest unit tests and excludes `frontend/e2e/**`; run Playwright via `npm run test:e2e`.
- **Frontend CI cache key**: `actions/cache` uses `frontend/package.json` (no root lockfile in repo for npm).

---

## Document map

| File | Use |
|------|-----|
| `README.md` | Human quick start, feature list, links |
| `DEPLOY.md` | VM setup, Cloudflare, origin PEM/key paths, compose commands |
| `GGG_API.md` | GGG OAuth registration, redirect URIs, flows |
| `SECURITY.md` | Checklist; disclosure via `SECURITY_CONTACT_EMAIL` (optional in `.env`) |
