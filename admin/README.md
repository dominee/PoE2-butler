# PoE2 Butler · Admin console

Read-only FastAPI service for operators: **dashboard** (headline metrics, backend
health strip, snapshot mix bars), user list, snapshot audit, Redis / queue
telemetry, and upstream probes. Deployed alongside the main backend on its own
Traefik subdomain.

## Database

Dashboard SQL uses **PostgreSQL** intervals (`NOW() - INTERVAL '7 days'`, etc.).
Point `ADMIN_DATABASE_URL` at the same Postgres instance the backend uses (read
credentials are fine). SQLite is not supported for these admin queries.

## Local dev

```bash
cd admin
uv sync
ADMIN_DATABASE_URL=postgresql+asyncpg://poe2b:poe2b@localhost:5432/poe2b \
ADMIN_REDIS_URL=redis://localhost:6379/0 \
ADMIN_BACKEND_BASE_URL=http://localhost:8000 \
uv run uvicorn admin.app.main:app --reload --port 8001
```

Static assets (including `admin.css`) are served from `/static/`; the Dockerfile
copies the whole `app/` tree (templates + `static/`).

Default credentials: user `admin`, password `admin`. **Always** override via
`ADMIN_PASSWORD_HASH` (bcrypt) in any non-dev deployment and set
`ADMIN_TOTP_SECRET` for a second factor.

Restrict network exposure via `ADMIN_IP_ALLOWLIST` (JSON list of CIDRs).

### Docker Compose and bcrypt hashes

bcrypt hashes contain `$` characters. Compose treats `$` as interpolation when it
expands values (for example `environment: ADMIN_PASSWORD_HASH: ${…}`, or the same
`.env` file used as `docker compose --env-file`). In `deploy/env/.env.dev` and
`.env.prod`, write each literal `$` in the hash as `$$`, and **do not wrap the hash
in quotes**—quoted values often leave `$$` unexpanded so bcrypt sees garbage.
`AdminSettings` also strips outer quotes and collapses `$$` → `$` as a fallback.

### Live dashboard refresh

- `ADMIN_DASHBOARD_REFRESH_SEC=0` (default): no JavaScript auto-poll; the
  Overview still loads a fresh bundle on **first render** (server-side). Use a
  normal browser reload to refresh numbers.
- `ADMIN_DASHBOARD_REFRESH_SEC>0` (e.g. `30`): the Overview shows **Refresh now**
  (one-shot `GET /admin/api/summary`) and **Start auto-refresh** (repeating poll
  every *N* seconds) plus **Stop auto-refresh**. Polling does **not** start
  automatically after login (operators choose when to poll or enable live
  updates).

**Price jobs (background)** on the same page includes arq function breakdown
(unpickle when possible), Redis `poe2b:price_job:*` / dedupe stats, a
**Throttles** table (PTTL for keys such as `tp3:ggg_trade:lock` and vendor
`next` slots), and **Sample jobs (latest)** with columns including **Updated**
(UTC) from the last `save_job_state` write in the backend.

## Routes

| Path | Purpose |
|------|---------|
| `GET /admin/login` · `POST /admin/login` | Form-based sign in (bcrypt + optional TOTP) |
| `GET /admin/` | **Dashboard:** totals, activity metrics, snapshot mix, Redis summary, backend probes |
| `GET /admin/api/summary` | JSON bundle for the same dashboard (session cookie required); used for optional auto-refresh |
| `GET /admin/users` | Recent users and their prefs |
| `GET /admin/snapshots` | Most recent snapshots across all users |
| `GET /admin/cache` | Redis (memory, clients, evicted/expired keys), price cache, arq queue |
| `GET /admin/upstream` | Backend `/healthz` and `/readyz` with latency, HTTP status, parsed `version` |
| `GET /admin/healthz` | Cheap liveness probe for Traefik |
| `GET /admin/logout` | Clear session cookie |

## Security

- IP allowlist middleware (`ADMIN_IP_ALLOWLIST=["10.0.0.0/8", ...]`)
- Strict-SameSite, HttpOnly session cookie signed with `ADMIN_SESSION_SECRET`
- CSP / frame denial headers on every response
- No secrets from the main backend are exposed — admin connects to its own
  read credentials.
