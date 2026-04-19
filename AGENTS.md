# AGENTS.md

Primary context file for AI agents contributing to **PoE2 Hideout Butler**. Read this before touching code. Human-facing docs live in `README.md`; the original brief is `INSTRUCTIONS.md`.

## Project summary

Public multi-user SPA that lets PoE2 players sign in with GGG OAuth2 and browse their characters, equipped gear, and stash tabs, with enriched item info, price estimates (poe.ninja), and PoE2 Trade deep-links.

## Locked-in architectural decisions

| Topic | Decision |
|---|---|
| Tenancy | Multi-user public (data isolation per GGG account is mandatory) |
| Frontend | React 18 + Vite + TypeScript, Tailwind, TanStack Query, Zustand |
| Backend | FastAPI, Python 3.12, `uv`, pydantic v2, Alembic, `arq` |
| Storage | PostgreSQL 16 (persistent) + Redis 7 (cache, sessions, rate-limit, queue) |
| Identity | GGG OAuth2 only; Authorization Code + PKCE + `state` |
| API shape | JSON only, read-mostly; writes limited to auth, refresh trigger, user prefs |
| Admin | Separate app (`admin/`), not behind GGG OAuth2, read-only v1 |
| Dev mock | `mock-ggg/` stubs GGG endpoints with fixtures for local dev and tests |
| Deploy | docker compose + Traefik + Let's Encrypt on a 1 vCPU / 1 GB DO droplet |
| Refresh policy | On login + manual `POST /api/refresh` with per-account 60 s cooldown |
| Leagues | Default to the current temp league; switchable via dropdown |
| Trade tolerances | Exact search &plusmn;10% (configurable); upgrade min = current &times; 0.95, no max |

## Folder map

```text
backend/
  app/
    api/             FastAPI routers (auth, me, leagues, characters, stashes, items, prices, refresh)
    clients/         ggg_client.py, poe_ninja.py
    domain/          Pydantic domain models (User, Item, Character, StashTab, PriceEstimate)
    services/        trade_url.py, snapshot.py, pricing.py, rate_limit.py
    db/              SQLAlchemy models, Alembic env
    security/        crypto.py (AES-GCM), sessions.py, csrf.py
    workers/         arq_worker.py (snapshot + price warm jobs)
    main.py          App factory + middleware wiring
    config.py        Pydantic settings
  tests/
  Dockerfile
  pyproject.toml

frontend/
  src/
    api/             HTTP client (fetch wrapper with CSRF + credentials: include)
    features/
      auth/          Login button, callback landing
      characters/    Character grid, paper-doll, ItemCard
      stashes/       Tab strip, grid, table view
      items/         Detail pane, trade link buttons
      prices/        Price badge
    store/           Zustand stores (filters, prefs, session)
    theme/           Tailwind tokens (PoE2-derived, not direct copies)
    routes.tsx
    main.tsx
  Dockerfile

admin/               Separate container; read-only observability
mock-ggg/            FastAPI + fixtures that emulate GGG's OAuth2 and item endpoints
deploy/
  compose/           docker-compose.dev.yml, docker-compose.prod.yml, traefik/
  env/               .env.example(s)
docs/                Supplementary docs (DISCORD_BOT_API.md, SECURITY.md, etc.)
```

## Non-negotiable rules

1. **Security before performance.** Every change must consider: does it leak tokens, weaken CSP, bypass CSRF, or log secrets?
2. **GGG tokens are always encrypted at rest** (AES-GCM, key from `APP_SECRET_KEY`).
3. **Session cookies** are `HttpOnly`, `Secure` (in prod), `SameSite=Lax`, and carry only a random Redis session id.
4. **Rate limits** must be respected: per-GGG-account token bucket, per-IP global bucket, per-user refresh cooldown.
5. **Backend is read-mostly**: only `/api/auth/*`, `/api/refresh`, `/api/prefs` and admin write endpoints perform state mutation.
6. **No secrets in the frontend bundle.** Config is injected at runtime by serving `config.json` from the API, or via build-time public env vars for non-sensitive values only.
7. **`INSTRUCTIONS.md` is the source of truth.** If this file disagrees with it, update this file.

## Testing expectations

- Backend: `pytest` for unit + API contract tests against `mock-ggg`.
- Frontend: Vitest for components + one Playwright smoke test per milestone.
- CI must pass before a milestone is considered done (lint + tests + audit).

## Milestone status

See the plan in `.cursor/plans/` and the issue tracker (once opened). Current in-progress milestone is tracked there; keep this list in sync with actual state.

- M0 Foundations
- M1 Auth + characters + gear
- M2 Item detail pane + trade links
- M3 Stash tabs + search/filters
- M4 Pricing via poe.ninja
- M5 Admin observability app
- M6 Prod deploy + Discord bot API contract
