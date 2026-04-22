# AGENTS.md — PoE2 Hideout Butler

AI-agent context file. Read this first when starting any coding session.

---

## 1. Project overview

**PoE2 Hideout Butler** is a multi-user SPA that lets Path of Exile 2 players view their characters' gear and stash contents online. It enriches item information with pricing, tier/roll quality data, and trade-site deep-links.

**Production domain:** apex **`hideoutbutler.com`**. Public services use `app.hideoutbutler.com` (SPA), `api.hideoutbutler.com` (API + OAuth callback), `admin.hideoutbutler.com` (admin). Staging API host for OAuth: `dev-api.hideoutbutler.com` (optional until DNS exists).

Key features:
- GGG OAuth2 login (Authorization Code + PKCE).
- Snapshot of characters, gear, and stash tabs stored in Postgres.
- Item detail pane: rarity-coloured border, tag-stripped property names, explicit mod tiers, roll quality bars, socketed-item (rune/soul-core) display.
- Activity log: diff of current vs previous snapshot; new (green) / changed (amber) indicators in grid and table views.
- Price estimates via poe.ninja (cached in Redis).
- Admin observability app (separate FastAPI + Jinja2, basic auth + TOTP + IP allowlist).

---

## 2. Repository layout

```
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
├── admin/            FastAPI + Jinja2 admin app (port 8001)
├── mock-ggg/         Dev mock of GGG OAuth2 + API (FastAPI, port 9000)
│   ├── app/fixtures/ users.json · characters.json · stashes.json
│   └── samples/      poe.ninja character exports + convert.py
├── deploy/
│   ├── compose/      docker-compose.dev.yml · docker-compose.prod.yml · Traefik configs
│   └── env/          .env.example · .env.dev (gitignored)
├── docs/
├── INSTRUCTIONS.md   Original requirements (do not edit)
├── AGENTS.md         This file
├── DEPLOY.md         Build & deploy runbook
└── GGG_API.md        GGG OAuth2 integration guide
```

---

## 3. Architecture

```
Browser
  └─ React SPA  (app.dev.hideoutbutler.com · prod: app.hideoutbutler.com)
       │  JSON API (credentials)
       └─ FastAPI backend  (api.dev.hideoutbutler.com · prod: api.hideoutbutler.com)
            ├─ PostgreSQL 16  (users, snapshots, tokens)
            ├─ Redis 7        (sessions, rate-limit counters, price cache, arq queue)
            └─ GGG API / mock-ggg  (OAuth2 + game data)
```

- **Traefik v3** handles routing in both dev and prod (subdomains, HTTPS/ACME in prod).
- **arq** worker runs in the same Docker image as the backend (`arq app.workers.arq_worker.WorkerSettings`).
- All GGG API calls are **server-side only**; tokens never reach the browser.

---

## 4. Key technical conventions

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
    prev_payload: Mapped[dict|None] # previous snapshot (for activity diff)
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

```
text-rarity-normal  text-rarity-magic  text-rarity-rare  text-rarity-unique
text-rarity-currency  text-rarity-gem  text-rarity-quest
border-rarity-*  (same names)
```

---

## 5. Key data flows

### Auth / first login
1. `GET /api/auth/login` → generates PKCE, stores state in Redis, redirects to GGG authorize URL.
2. GGG → `GET /api/auth/callback?code=&state=` → exchanges code, upserts `User` + `UserToken`, triggers `refresh_user_snapshot` in a separate `snap_db` session, sets session cookie.
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

## 6. Environment variables (key subset)

| Variable | Purpose |
|---|---|
| `APP_SECRET_KEY` | AES-GCM key for token encryption (32 bytes, base64) |
| `SESSION_SIGNING_KEY` | Cookie signing key |
| `GGG_CLIENT_ID` / `GGG_CLIENT_SECRET` | GGG OAuth2 credentials |
| `GGG_OAUTH_BASE_URL` | Internal (server-to-server) GGG base URL |
| `GGG_OAUTH_AUTHORIZE_BASE_URL` | Browser-facing authorize URL — set in `.env.dev` to `http://ggg.dev.hideoutbutler.com`; empty in prod (falls back to `GGG_OAUTH_BASE_URL`) |
| `GGG_REDIRECT_URI` | Dev: `http://app.dev.hideoutbutler.com/api/auth/callback` · Prod: `https://app.hideoutbutler.com/api/auth/callback` |
| `CORS_ALLOW_ORIGINS` | JSON array, e.g. `["http://app.dev.hideoutbutler.com"]` |
| `PRICING_SOURCE` | `static` (dev) or `poe_ninja` |
| `DEFAULT_VALUABLE_THRESHOLD_CHAOS` | Starting threshold for valuable item highlights |

---

## 7. Database migrations

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

## 8. Mock GGG service

Located in `mock-ggg/`. Fixture data in `mock-ggg/app/fixtures/`.

To regenerate fixture data from poe.ninja exports:

```bash
cd mock-ggg/samples
python convert.py  # reads *.json, writes ../app/fixtures/characters.json
```

The first entry in `users.json` is auto-selected on the mock login form.

---

## 9. Pending work (as of 2026-04-19)

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

## 10. Known gotchas

- **OAuth callback host**: `GGG_REDIRECT_URI` points to the **app** host (`app.dev.hideoutbutler.com/api/auth/callback`). The Vite dev server proxies `/api/*` → backend, so the Set-Cookie response is scoped to the SPA origin. All subsequent API calls go through the same proxy — no cross-origin cookie issues.
- **Enum mapping**: `Snapshot.kind` uses `values_callable=lambda e: [m.value for m in e]` + `create_type=False` to avoid `snapshot_kind` type conflicts across Alembic runs.
- **Transaction isolation**: `refresh_user_snapshot` runs in a separate `snap_db` session committed before the main auth session is committed — prevents `InFailedSQLTransactionError` on snapshot write errors.
- **CORS**: `CORS_ALLOW_ORIGINS` must be a JSON array string, e.g. `["http://app.dev.hideoutbutler.com"]`.
- **Bcrypt hashes in env files**: `$` must be escaped as `$$` in docker-compose `--env-file` files.
- **Traefik dev**: uses static file provider (`dynamic.dev.yml`), not the Docker provider — avoids Docker socket security exposure in dev.
- **Frontend unit test scope**: `npm test` runs Vitest unit tests and excludes `frontend/e2e/**`; run Playwright via `npm run test:e2e`.
