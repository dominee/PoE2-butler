# PoE2 Butler · Admin console

Read-only FastAPI service for operators: user list, snapshot stats, Redis and
queue telemetry, and upstream health probes. Deployed alongside the main
backend on its own Traefik subdomain.

## Local dev

```bash
cd admin
uv sync
ADMIN_DATABASE_URL=postgresql+asyncpg://poe2b:poe2b@localhost:5432/poe2b \
ADMIN_REDIS_URL=redis://localhost:6379/0 \
ADMIN_BACKEND_BASE_URL=http://localhost:8000 \
uv run uvicorn admin.app.main:app --reload --port 8001
```

Default credentials: user `admin`, password `admin`.  **Always** override via
`ADMIN_PASSWORD_HASH` (bcrypt) in any non-dev deployment and set
`ADMIN_TOTP_SECRET` for a second factor.

Restrict network exposure via `ADMIN_IP_ALLOWLIST` (JSON list of CIDRs).

## Routes

| Path | Purpose |
|------|---------|
| `GET /admin/login` · `POST /admin/login` | Form-based sign in (bcrypt + optional TOTP) |
| `GET /admin/` | Totals, snapshots by kind, redis + queue summary |
| `GET /admin/users` | Recent users and their prefs |
| `GET /admin/snapshots` | Most recent snapshots across all users |
| `GET /admin/cache` | Redis, price cache, arq queue |
| `GET /admin/upstream` | Probes backend `/healthz` and `/readyz` |
| `GET /admin/healthz` | Cheap liveness probe for Traefik |
| `GET /admin/logout` | Clear session cookie |

## Security

- IP allowlist middleware (`ADMIN_IP_ALLOWLIST=["10.0.0.0/8", ...]`)
- Strict-SameSite, HttpOnly session cookie signed with `ADMIN_SESSION_SECRET`
- CSP / frame denial headers on every response
- No secrets from the main backend are exposed — admin connects to its own
  read credentials.
