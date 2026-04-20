# PoE2 Hideout Butler

> *"Think of it as your personal PoE2 Hideout butler who takes care of your gear and stash."*

A web application that lets **Path of Exile 2** players pair their GGG account via OAuth2, then browse their characters, equipped gear, and stash tabs online with enriched item information, price estimates, and one-click deep-links to the official trade site.

![Screenshot](Screenshot.png)

## Features

- Sign in with your GGG account (OAuth2 + PKCE).
- Browse characters per league and inspect equipped gear in a paper-doll view.
- Browse stash tabs (including currency and other special tab types) in an in-game-like grid or as a virtualised table.
- Click any item to open a detail pane with the full mod list, requirements, sockets/runes, source, and actions.
- Generate PoE2 Trade search links for **the same item** (configurable stat tolerance, default &plusmn;10%) and for **upgrades** (min = current &times; 0.95, no max).
- Price estimates via cached 3rd-party data (poe.ninja), with optional "valuable dump" highlighting for offline price-checks.

## Stack

| Layer | Choice |
|---|---|
| Frontend | React 18 + Vite + TypeScript, Tailwind CSS, TanStack Query, Zustand |
| Backend | Python 3.12, FastAPI, `uv`, Alembic, `arq`, `httpx`, pydantic v2 |
| Storage | PostgreSQL 16 + Redis 7 |
| Edge | Traefik v3 with Let's Encrypt (production) |
| Tests | `pytest`, Vitest, Playwright |

## Repository layout

```text
backend/      FastAPI app, domain models, GGG + poe.ninja clients
frontend/     React SPA
admin/        Separate FastAPI + minimal React admin (observability only)
mock-ggg/     Local mock of GGG OAuth2 + API for development and tests
deploy/       docker-compose files, Traefik config, env templates
docs/         Supplementary docs referenced by the top-level MDs
```

## Quick start (development)

```bash
cp deploy/env/.env.example deploy/env/.env.dev
docker compose -f deploy/compose/docker-compose.dev.yml --env-file deploy/env/.env.dev up --build
```

Once containers are healthy:

- Frontend: <http://app.localhost>
- API: <http://api.localhost>
- Mock GGG: <http://ggg.localhost>
- Traefik dashboard: <http://localhost:8080>

Add `127.0.0.1 app.localhost api.localhost ggg.localhost` to `/etc/hosts` if your resolver does not already handle `.localhost`.

## Documentation

- [INSTRUCTIONS.md](INSTRUCTIONS.md) — original user brief (do not edit).
- [AGENTS.md](AGENTS.md) — context for AI agents contributing to the project.
- [GGG_API.md](GGG_API.md) — GGG OAuth2 setup, scopes, rate-limits.
- [DEPLOY.md](DEPLOY.md) — build and deploy procedure.
- [SECURITY.md](SECURITY.md) — cross-cutting security checklist.
- [docs/BOT_API.md](docs/BOT_API.md) — frozen contract for external API consumers (e.g. Discord bot).
- [docs/openapi.json](docs/openapi.json) — pinned OpenAPI 3.1 schema.

## License

See [LICENSE](LICENSE).
