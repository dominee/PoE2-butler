# Deployment Guide

Build and deploy procedure for **PoE2 Hideout Butler**.

## Environments

| Name | Stack | Domain pattern |
|---|---|---|
| Local dev | `deploy/compose/docker-compose.dev.yml` with `mock-ggg` | `*.localhost` via Traefik |
| Remote DEV | `docker-compose.prod.yml` with `.env.dev` | `dev-app.<domain>`, `dev-api.<domain>`, `dev-admin.<domain>` |
| PROD | `docker-compose.prod.yml` with `.env.prod` | `app.<domain>`, `api.<domain>`, `admin.<domain>` |

Both remote stacks run on the **same 1 vCPU / 1 GB VM** and are routed by a single shared Traefik instance.

## Target VM sizing

Budget for the 1 vCPU / 1 GB / 25 GB / 1 TB egress class:

| Service | Budget | Notes |
|---|---|---|
| Traefik | ~50 MB | hard limit 96 MB |
| Backend (uvicorn, 2 workers) | ~220 MB | hard limit 256 MB |
| Arq worker | ~110 MB | hard limit 128 MB |
| Frontend (nginx-alpine serving static bundle) | ~10 MB | hard limit 64 MB |
| Admin console | ~50 MB | hard limit 64 MB |
| Postgres | ~200 MB RSS | `shared_buffers=128MB`, limit 320 MB |
| Redis | ~140 MB RSS | `maxmemory 128mb` + `allkeys-lru`, limit 160 MB |
| **Total** | **~780 MB** | leaves ~240 MB for page cache / kernel |

A `swapfile` of 2 GB is strongly recommended as a safety net.

## First-time VM bootstrap

1. Create the droplet, add the deploy SSH key, note the public IP.
2. Point A records:
   - `app.<domain>`, `api.<domain>`, `admin.<domain>`
   - `dev-app.<domain>`, `dev-api.<domain>`, `dev-admin.<domain>`
3. SSH in as root, create an unprivileged `deploy` user with sudo, disable
   password auth, enable UFW: allow `22`, `80`, `443`.
4. Install Docker Engine + compose plugin. Add `deploy` to the `docker` group.
5. Create `/opt/poe2-butler`, clone this repo as `deploy`, and copy env files:

   ```bash
   cp deploy/env/.env.example deploy/env/.env.prod
   cp deploy/env/.env.example deploy/env/.env.dev
   chmod 600 deploy/env/.env.*
   ```

6. Fill in real secrets (see **Secrets** below) and domain names.
7. Run the stack:

   ```bash
   docker compose \
     -f deploy/compose/docker-compose.prod.yml \
     --env-file deploy/env/.env.prod \
     up -d --build
   ```

8. Apply database migrations (one-off):

   ```bash
   docker compose -f deploy/compose/docker-compose.prod.yml \
     --env-file deploy/env/.env.prod \
     exec backend alembic upgrade head
   ```

9. Verify Traefik obtained certificates:

   ```bash
   docker logs poe2b-traefik | grep -i acme
   curl -I https://api.<domain>/healthz
   ```

## Secrets to populate per environment

| Variable | Notes |
|---|---|
| `APP_SECRET_KEY` | 32 random bytes, base64-encoded. Used for AES-GCM token encryption. |
| `SESSION_SIGNING_KEY` | 32 random bytes, base64. Used to sign session cookies. |
| `GGG_CLIENT_ID` / `GGG_CLIENT_SECRET` / `GGG_REDIRECT_URI` | From GGG after the OAuth2 application is approved. |
| `POSTGRES_PASSWORD` | Strong random. |
| `ADMIN_USERNAME` / `ADMIN_PASSWORD_HASH` | Admin login; hash is bcrypt (`bcrypt.hashpw`). |
| `ADMIN_TOTP_SECRET` | Optional; enables TOTP on admin login. |
| `ADMIN_SESSION_SECRET` | 32 random bytes; signs the admin session cookie. |
| `ADMIN_IP_ALLOWLIST` | JSON list of CIDRs, e.g. `["203.0.113.0/24"]`. |
| `TRAEFIK_ACME_EMAIL` | For Let's Encrypt. |
| `APP_DOMAIN` / `API_DOMAIN` / `ADMIN_DOMAIN` | Full hostnames per environment. |

Generating values:

```bash
# Random 32-byte base64 keys
openssl rand -base64 32

# Bcrypt hash for admin
python -c 'import bcrypt,getpass; \
  p=getpass.getpass().encode(); \
  print(bcrypt.hashpw(p, bcrypt.gensalt()).decode())'

# TOTP secret (scan into an authenticator app)
python -c 'import pyotp; print(pyotp.random_base32())'
```

## Rolling updates

Image swap with health-check preservation (no blue/green needed at this scale):

```bash
cd /opt/poe2-butler
git pull

COMPOSE="docker compose \
  -f deploy/compose/docker-compose.prod.yml \
  --env-file deploy/env/.env.prod"

# Pull pre-built images (or build locally if not using the registry)
$COMPOSE pull backend worker frontend admin || $COMPOSE build

# Migrate schema first (idempotent)
$COMPOSE run --rm backend alembic upgrade head

# Roll services one at a time, leaving dependencies untouched.
$COMPOSE up -d --no-deps backend
$COMPOSE up -d --no-deps worker
$COMPOSE up -d --no-deps frontend admin

$COMPOSE ps
```

Watch `docker logs -f poe2b-backend` during the swap and curl `https://api.<domain>/healthz`.

## Backups & restore drill

### Postgres

Nightly `pg_dump` via host cron (drop the following into `/etc/cron.d/poe2b-pgdump`):

```
15 3 * * * deploy /usr/bin/docker exec poe2b-postgres \
  pg_dump -U $POSTGRES_USER $POSTGRES_DB \
  | gzip > /opt/poe2-butler/backups/pg/poe2b-$(date +\%Y\%m\%d).sql.gz
```

Retain at least 14 daily dumps plus a weekly offsite copy via `rclone`.

### Redis

Cache-only; not backed up. A cold start re-populates prices and sessions on demand.

### Restore drill (run quarterly)

```bash
# 1. Spin up a disposable stack pinned to the current release
cp -r /opt/poe2-butler /tmp/poe2b-drill
cd /tmp/poe2b-drill

# 2. Restore the most recent dump into a fresh Postgres container
gunzip -c /opt/poe2-butler/backups/pg/poe2b-<YYYYMMDD>.sql.gz \
  | docker compose -f deploy/compose/docker-compose.prod.yml \
      --env-file deploy/env/.env.prod \
      exec -T postgres psql -U $POSTGRES_USER -d $POSTGRES_DB

# 3. Run the backend smoke tests against the restored stack
docker compose run --rm backend uv run pytest tests/test_health.py -q

# 4. Tear down the drill stack
docker compose down -v
```

Record the drill date in `docs/RESTORE_DRILL_LOG.md`.

## CI/CD

- GitHub Actions runs lint + tests + `pip-audit` + `npm audit` on every PR (backend, admin, frontend, mock-ggg).
- `main` builds tagged images (`ghcr.io/<owner>/poe2b-{backend,frontend,admin}:<sha>`) which the rolling update command pulls.
- Manual promotions for now: operator SSH in, `git pull`, run the rolling update. A self-hosted runner can be wired later.

## OpenAPI contract & Discord bot consumers

- The backend ships an OpenAPI 3.1 schema at `GET /openapi.json` (FastAPI default). This is the canonical contract.
- A frozen copy for external consumers — including the future Discord bot — lives at `docs/openapi.json` and is updated via:

  ```bash
  cd backend
  uv run python -c \
    'import json; from app.main import app; print(json.dumps(app.openapi(), indent=2))' \
    > ../docs/openapi.json
  ```

  Refresh on every milestone-closing commit.

- Bot-facing endpoint contract is documented in `docs/BOT_API.md`.

## Suggested subdomain scheme

| Sub | Service |
|---|---|
| `app.<d>` | Frontend SPA |
| `api.<d>` | Public backend API |
| `admin.<d>` | Admin observability UI |
| `dev-app.<d>`, `dev-api.<d>`, `dev-admin.<d>` | Same, for DEV stack |
