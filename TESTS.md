# Testing

This document describes the automated tests in the repository and how to run them locally on a **development** machine (the same stack as [README.md](README.md) Quick start: Traefik, `app.dev.hideoutbutler.com`, `mock-ggg`, and so on).

CI mirrors most of this in [`.github/workflows/ci.yml`](.github/workflows/ci.yml). Dependency audits in that workflow are informational and not treated as a required “test suite” here.

The repository root [Makefile](Makefile) wraps the same commands: `make test` (all non-E2E checks by category), `make test-e2e`, `make up` / `make down` for the dev stack, and `make help` for a full list.

---

## What is covered

| Area | Technology | What it exercises |
|------|------------|-------------------|
| **Backend** | `pytest` + `pytest-asyncio`, Ruff | FastAPI routes (including in-process “stack” tests with the real [mock-ggg](mock-ggg) app, FakeRedis, and SQLite), domain parsing, trade URL / pricing helpers, security/crypto helpers, health and CDN proxy, public shares, item text API, and [`GET /api/activity`](backend/app/api/activity.py). |
| **Admin** | `pytest`, Ruff | `SessionManager` (bcrypt, session token issue/validate, TOTP gating) in [admin/tests/](admin/tests/). |
| **mock-ggg** | Ruff | Lint only in CI; no test runner in the mock service itself. |
| **Frontend** | Vitest + Testing Library, ESLint (CI allows failures), `tsc -b` | Components (items, landing, `CharacterStatSummary`, …), and pure utilities (clipboard, `poecdn`, stash [filters](frontend/src/features/stashes/filters.test.ts)). |
| **E2E** | Playwright | [frontend/e2e/login.spec.ts](frontend/e2e/login.spec.ts): landing → mock OAuth → `/app` with a fixture character. [frontend/e2e/stash-item.spec.ts](frontend/e2e/stash-item.spec.ts): same login, then Stash view, a stash tab, and the item detail pane. |

**Not covered here:** broad UI coverage of every feature; Playwright is intentionally a small browser smoke. Backend tests avoid requiring Docker or a live PostgreSQL/Redis for the default `pytest` run (see [backend/tests/test_auth_flow.py](backend/tests/test_auth_flow.py) fixtures).

---

## Prerequisites (local)

- **Python 3.12+** and **[uv](https://docs.astral.sh/uv/)** for `backend/`, `admin/`, and `mock-ggg/`.
- **Node.js 22** and `npm` for `frontend/`. A plain `make test` from an IDE or a non-interactive environment may not see the same `PATH` as your shell (for example, Homebrew is often under `/opt/homebrew/bin`). The root [Makefile](Makefile) prepends that path and includes a `require-npm` check; if you use **nvm**, run `source ~/.nvm/nvm.sh` in the terminal, then `make` again, or set `PATH` to include the directory that contains `npm`.
- **Docker** and Docker Compose, only if you want to run the **Playwright** flows against the full dev stack.
- For browser tests: resolve Traefik dev hostnames to your machine (e.g. `/etc/hosts` or DNS), as in [README.md](README.md).

---

## Run unit and integration tests (no Docker)

From the **repository root**, after installing dependencies once per project:

### Backend

```bash
cd backend
uv sync
uv run ruff check .
uv run pytest -ra
```

### Admin

```bash
cd admin
uv sync
uv run ruff check .
uv run pytest -ra
```

### mock-ggg (lint only)

```bash
cd mock-ggg
uv sync
uv run ruff check .
```

### Frontend

```bash
cd frontend
npm install   # or: npm ci  if you use a lockfile and want CI-identical deps
npm run lint
npx tsc -b
npm test
```

`npm test` runs **Vitest** in run mode (`vitest run`). Use `npm run test:watch` for interactive runs.

To match CI loosely (CI uses `npm run lint || true`), you can run lint; fixing lint is recommended even when CI does not block on it.

---

## One-shot: all non-E2E checks from the repo root

If your shell is at the repository root and `uv` / `npm` are on your `PATH`:

```bash
( cd backend   && uv sync && uv run ruff check . && uv run pytest -ra ) && \
( cd admin     && uv sync && uv run ruff check . && uv run pytest -ra ) && \
( cd mock-ggg  && uv sync && uv run ruff check . ) && \
( cd frontend  && npm install && npm run lint && npx tsc -b && npm test ) && \
echo "All non-E2E tests passed"
```

Run each block separately if you prefer clearer failure output.

---

## Playwright (E2E) on the **dev** stack

Playwright needs the app reachable at the same host the browser will use. The default in [frontend/playwright.config.ts](frontend/playwright.config.ts) is `http://app.dev.hideoutbutler.com` (override with `PLAYWRIGHT_BASE_URL`).

### 1. Start the stack and apply migrations

Bring the dev compose stack up (see [README.md](README.md) for copying and editing `deploy/env/.env.dev`):

```bash
docker compose -f deploy/compose/docker-compose.dev.yml --env-file deploy/env/.env.dev up -d --build
```

**First time (or new DB):** run Alembic inside the backend container so API routes that touch the database work for OAuth and stash:

```bash
docker compose -f deploy/compose/docker-compose.dev.yml --env-file deploy/env/.env.dev exec backend alembic upgrade head
```

(Use the same `--env-file` you used for `up`.)

If you do not have a `deploy/env/.env.dev` yet, you can start from the committed E2E-oriented template and adjust for your machine:

```bash
cp deploy/env/.env.e2e deploy/env/.env.dev
# Then edit as needed, or use as-is for local E2E-only runs.
```

### 2. Hostnames

Point **app**, **api**, and **ggg** dev hostnames at `127.0.0.1` (see README). Without this, the browser and OAuth redirect targets will not match the Traefik routes.

### 3. Install Playwright browsers (once per machine / CI image)

```bash
cd frontend
npm install
npx playwright install --with-deps chromium
```

On Linux, `--with-deps` installs system libraries the browser needs.

### 4. Run E2E tests

```bash
cd frontend
# Optional: explicit base URL
export PLAYWRIGHT_BASE_URL=http://app.dev.hideoutbutler.com
npm run test:e2e
```

This runs all specs under [frontend/e2e/](frontend/e2e/) (including login and stash/item flows). Stop the stack when finished if you do not need it: `docker compose -f deploy/compose/docker-compose.dev.yml --env-file deploy/env/.env.dev down`.

---

## What CI runs (summary)

- **backend / admin / mock-ggg:** `uv sync`, Ruff, `pytest` where applicable.
- **frontend:** `npm install`, `npm run lint` (non-blocking in CI), `npx tsc -b`, `npm test`.
- **e2e:** same compose pattern as above with [deploy/env/.env.e2e](deploy/env/.env.e2e) copied to `.env.dev`, `/etc/hosts` entries, API wait + `alembic upgrade head`, then Playwright against the app host.

---

## Tips

- If Playwright times out on first load, the Vite dev server inside Docker can be slow to compile; re-run or increase per-test timeout in the spec.
- If stash tabs are empty in E2E, the specs may trigger an app **Refresh** (global snapshot refresh) before asserting on stash; ensure the mock user and GGG flow complete successfully and migrations have been applied.
