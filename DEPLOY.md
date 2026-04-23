# DEPLOY.md — Build & Deploy Runbook

PoE2 Hideout Butler deployment guide for local development and production (DigitalOcean Droplet).

---

## 1. Prerequisites

| Tool | Min version | Purpose |
|---|---|---|
| Docker Desktop / Docker Engine | 26+ | Container runtime |
| Docker Compose plugin | v2.24+ | Orchestration |
| `openssl` | any | Generating secrets |
| `bcrypt` (Python) | any | Hashing admin password |

---

## 2. Local development

### 2.1 First-time setup

```bash
# Clone
git clone https://github.com/<you>/PoE2-butler.git
cd PoE2-butler

# Copy and customise the env file
cp deploy/env/.env.example deploy/env/.env.dev
# Edit .env.dev if needed (defaults work out of the box for local dev)
```

### 2.2 Build and start

```bash
docker compose \
  -f deploy/compose/docker-compose.dev.yml \
  --env-file deploy/env/.env.dev \
  up --build
```

Services and their local URLs:

| Service | URL | Notes |
|---|---|---|
| Frontend (Vite HMR) | http://app.localhost | SPA |
| Backend (FastAPI) | http://api.localhost | JSON API + docs at `/docs` |
| Mock GGG | http://ggg.localhost | OAuth2 + fixture data |
| Admin | http://admin.localhost | Basic auth + TOTP |
| Traefik dashboard | http://localhost:8080 | Routing overview |

> **Note**: `*.localhost` subdomains resolve on most Linux/macOS/Windows hosts via the system resolver. If they don't, add entries to `/etc/hosts`:
> ```
> 127.0.0.1  app.localhost api.localhost ggg.localhost admin.localhost
> ```

### 2.3 Apply database migrations

Run once after first start, and after any schema change:

```bash
docker compose \
  -f deploy/compose/docker-compose.dev.yml \
  --env-file deploy/env/.env.dev \
  exec backend alembic upgrade head
```

### 2.4 Regenerating mock fixtures

After adding new poe.ninja character exports to `mock-ggg/samples/`:

```bash
cd mock-ggg/samples
python convert.py
cd ../..

# Rebuild only the mock-ggg image
docker compose \
  -f deploy/compose/docker-compose.dev.yml \
  --env-file deploy/env/.env.dev \
  up --build mock-ggg -d
```

### 2.5 Rebuilding a single service

```bash
docker compose \
  -f deploy/compose/docker-compose.dev.yml \
  --env-file deploy/env/.env.dev \
  up --build backend -d
```

### 2.6 Running backend tests locally

```bash
cd backend
uv sync
uv run pytest
```

### 2.7 Linting

```bash
# Backend
cd backend && uv run ruff check . && uv run ruff format --check .

# Frontend
cd frontend && npm run lint
```

---

## 3. Environment variables

All variables documented in `deploy/env/.env.example`. Copy to `.env.dev` (dev) or `.env.prod` (prod) and fill in secrets.

### Generating secrets

```bash
# APP_SECRET_KEY (32 random bytes, base64)
openssl rand -base64 32

# SESSION_SIGNING_KEY
openssl rand -base64 32

# ADMIN_SESSION_SECRET
openssl rand -base64 32

# ADMIN_TOTP_SECRET (RFC 4648 base32)
python -c "import base64, os; print(base64.b32encode(os.urandom(20)).decode())"

# ADMIN_PASSWORD_HASH
python -c "import bcrypt; print(bcrypt.hashpw(b'yourpassword', bcrypt.gensalt()).decode())"
```

> **Important**: bcrypt hashes contain `$` characters. In docker-compose `--env-file` files each `$` must be escaped as `$$`.

---

## 4. Production deployment (DigitalOcean Droplet)

Target VM: **DigitalOcean Basic, Premium AMD, 1 vCPU / 1 GB RAM / 25 GB disk**.

### 4.1 Initial VM setup

```bash
# SSH in (replace with your droplet IP and key path)
ssh -i ~/.ssh/id_ed25519 root@<DROPLET_IP>

# System packages
apt-get update && apt-get upgrade -y
apt-get install -y git curl

# Install Docker (official script)
curl -fsSL https://get.docker.com | sh
usermod -aG docker $USER
newgrp docker

# Verify
docker compose version
```

### 4.2 Deploy the application

```bash
# On the VM
git clone https://github.com/<you>/PoE2-butler.git /opt/poe2-butler
cd /opt/poe2-butler

# Create the prod env file
cp deploy/env/.env.example deploy/env/.env.prod
# Fill in all required secrets (see section 3)
nano deploy/env/.env.prod
```

Required variables for prod (in addition to defaults):

| Variable | Value |
|---|---|
| `APP_SECRET_KEY` | Random 32-byte base64 |
| `SESSION_SIGNING_KEY` | Random 32-byte base64 |
| `POSTGRES_PASSWORD` | Strong random password |
| `GGG_CLIENT_ID` | From GGG developer approval |
| `GGG_CLIENT_SECRET` | From GGG developer approval |
| `GGG_OAUTH_BASE_URL` | `https://www.pathofexile.com` |
| `GGG_API_BASE_URL` | `https://api.pathofexile.com` |
| `GGG_REDIRECT_URI` | `https://api.hideoutbutler.com/api/auth/callback` |
| `CORS_ALLOW_ORIGINS` | `["https://app.hideoutbutler.com"]` |
| `API_DOMAIN` | `api.hideoutbutler.com` |
| `APP_DOMAIN` | `app.hideoutbutler.com` |
| `ADMIN_DOMAIN` | `admin.hideoutbutler.com` |
| `SECURITY_CONTACT_EMAIL` | Optional; ops / security contact (not consumed by Traefik) |
| `ADMIN_PASSWORD_HASH` | bcrypt hash (escape `$` → `$$`) |
| `ADMIN_TOTP_SECRET` | base32 secret |
| `ADMIN_SESSION_SECRET` | Random 32-byte base64 |
| `GITHUB_OWNER` | Your GitHub username (for image tags) |

Before first boot, install **Cloudflare Origin CA** TLS material on the VM (next subsection).

### 4.3 Cloudflare: DNS, proxy, and origin certificates

Production assumes **[Cloudflare](https://www.cloudflare.com/)** sits in front of the VM (orange-cloud **proxied** records). Public HTTPS is terminated at Cloudflare; Traefik serves HTTPS on the origin using a **Cloudflare Origin Certificate** so Cloudflare can connect with **Full (strict)** mode.

1. **DNS** — In Cloudflare, create **A** records for the app, API, and admin hostnames pointing to `<DROPLET_IP>`, with the proxy enabled (orange cloud). Example:

   ```
   app.hideoutbutler.com    A  <DROPLET_IP>  (proxied)
   api.hideoutbutler.com    A  <DROPLET_IP>  (proxied)
   admin.hideoutbutler.com  A  <DROPLET_IP>  (proxied)
   ```

   Optional staging (if used for GGG `dev-api` redirect):

   ```
   dev-api.hideoutbutler.com  A  <DROPLET_IP>  (proxied)
   ```

2. **SSL/TLS** — Set encryption mode to **Full (strict)** (SSL/TLS → Overview). Do not use “Flexible” (it would downgrade origin to HTTP).

3. **Origin certificate** — In Cloudflare: **SSL/TLS** → **Origin Server** → **Create certificate**. Include hostnames for this stack, e.g. `app.hideoutbutler.com`, `api.hideoutbutler.com`, `admin.hideoutbutler.com` (or a single wildcard you prefer). Use the default 15-year Origin CA, PEM format.

4. **Install files on the VM** — Save the certificate and private key on the host (not in git):

   ```bash
   sudo install -d -m 0750 /opt/poe2-butler/deploy/compose/traefik/certs
   # Paste Cloudflare’s certificate → cloudflare-origin.pem
   # Paste private key               → cloudflare-origin.key
   sudo chmod 0640 /opt/poe2-butler/deploy/compose/traefik/certs/cloudflare-origin.{pem,key}
   ```

   Paths and filenames must match `deploy/compose/traefik/dynamic.prod.yml` (mounted read-only at `/certs` in the Traefik container). Regenerate the origin certificate in Cloudflare when you add hostnames to the same origin.

5. **Client IP (optional)** — With the proxy on, your apps see Cloudflare’s IPs unless you [restore visitor IPs](https://developers.cloudflare.com/fundamentals/reference/http-request-headers/#cf-connecting-ip) (e.g. `CF-Connecting-IP` or Traefik `forwardedHeaders` with [Cloudflare IP ranges](https://www.cloudflare.com/ips/)).

### 4.4 Start the production stack

```bash
cd /opt/poe2-butler

docker compose \
  -f deploy/compose/docker-compose.prod.yml \
  --env-file deploy/env/.env.prod \
  up -d --build

# Apply migrations
docker compose \
  -f deploy/compose/docker-compose.prod.yml \
  --env-file deploy/env/.env.prod \
  exec backend alembic upgrade head
```

**Verify Traefik is listening for HTTPS (required for Cloudflare → origin):** the **production** compose file publishes `80` and `443` on the Traefik container, not `8080`. A healthy prod `poe2b-traefik` should look like this:

```text
0.0.0.0:80->80/tcp, 0.0.0.0:443->443/tcp
```

If you only see `80` and `8080` and **no** `443`, you are on the **development** stack (`docker-compose.dev.yml`) or an **old** prod compose that omitted the host port. Use `deploy/compose/docker-compose.prod.yml` and `docker compose ... up -d --force-recreate traefik` after adding `443:443`. On the VM, ensure nothing else binds to host `:443` before starting Traefik.

### 4.5 Updating to a new version

```bash
cd /opt/poe2-butler

git pull

docker compose \
  -f deploy/compose/docker-compose.prod.yml \
  --env-file deploy/env/.env.prod \
  up -d --build

# Apply any new migrations
docker compose \
  -f deploy/compose/docker-compose.prod.yml \
  --env-file deploy/env/.env.prod \
  exec backend alembic upgrade head
```

### 4.6 UAT environment (mock GGG + public HTTPS)

**UAT** is for acceptance testing on a **public** VM with **Cloudflare** in front and **Origin CA** TLS to Traefik, while the stack still uses **`mock-ggg`** and dev-like OAuth client IDs (not real GGG). It is defined in `deploy/compose/docker-compose.uat.yml` and `deploy/compose/traefik/{traefik.uat,dynamic.uat}.yml`.

- **Isolated project**: Compose project name `poe2b-uat` with separate Docker networks (`poe2b_uat_edge`, `poe2b_uat_internal`) and **prefixed** container names (`poe2b-uat-*`) so you can run UAT on the same host as dev/prod without network clashes.
- **No Docker socket in Traefik** (static routes only, like dev).
- **App host** `app.uat.hideoutbutler.com` routes `PathPrefix(/api)` to the **backend** and the rest to the **static** SPA, so the browser can keep **same-origin** `fetch("/api/...")` and OAuth `GGG_REDIRECT_URI` on `https://app.uat.../api/auth/callback` (analogous to the Vite proxy in dev).
- **Worker** (`arq`) is included for snapshot jobs.

**Setup**

1. In Cloudflare, add proxied A records e.g. `app.uat`, `ggg.uat`, `admin.uat` under your zone (or a delegated sub-zone) pointing to the UAT droplet. SSL mode: **Full (strict)**.
2. Issue or re-use a Cloudflare **Origin** certificate that covers `app.uat.hideoutbutler.com`, `ggg.uat.hideoutbutler.com`, and `admin.uat.hideoutbutler.com` (a **`*.uat.hideoutbutler.com` wildcard** is typical). Place PEM + key in `deploy/compose/traefik/certs/` as `cloudflare-origin.pem` and `cloudflare-origin.key` (same filenames as production; use a **separate** UAT keypair if the prod and UAT origins differ).
3. On the host:

   ```bash
   cp deploy/env/.env.uat.example deploy/env/.env.uat
   # Edit: secrets, POSTGRES_PASSWORD, ADMIN_*, etc.

   docker compose -f deploy/compose/docker-compose.uat.yml --env-file deploy/env/.env.uat up -d --build

   docker compose -f deploy/compose/docker-compose.uat.yml --env-file deploy/env/.env.uat \
     exec backend alembic upgrade head
   ```

4. `docker ps` should show `poe2b-uat-traefik` with `80` and `443` published (not `8080`).

5. **404 from Traefik** (access log `RequestHost` present, `OriginStatus:0`): the **Host** header must match a rule in `dynamic.uat.yml`. The UAT file defines **one router per hostname** (no `||` in rules) for `app.uat…`, `app.…`, the **apex** `hideoutbutler.com`, **`www.hideoutbutler.com`**, and ggg/admin variants. If you see `RequestHost: hideoutbutler.com`, the apex must be both in **DNS** and on the **Origin certificate** SANs, and you must **recreate Traefik** after editing: `docker compose ... up -d --force-recreate traefik`. Set `APP_BASE_URL`, `CORS_ALLOW_ORIGINS`, and `GGG_REDIRECT_URI` in `.env.uat` to match the **exact** origin users use (including apex or `www` if applicable).

6. If you need another hostname, add two routers in `dynamic.uat.yml` (one for `PathPrefix(/api)`, one for the SPA) and extend the Cloudflare Origin certificate.

---

## 5. Secret rotation

### APP_SECRET_KEY (AES-GCM token encryption key)

Rotating this key invalidates **all stored GGG tokens**. Users will need to re-authenticate.

1. Generate new key: `openssl rand -base64 32`
2. Update `APP_SECRET_KEY` in the env file.
3. Restart the backend: `docker compose ... restart backend worker`
4. Users will be prompted to log in again on next visit.

### SESSION_SIGNING_KEY

Rotating invalidates all active sessions (users are logged out).

### ADMIN_TOTP_SECRET

1. Generate a new base32 secret.
2. Re-enrol your authenticator app.
3. Update env and restart admin.

---

## 6. Observability

### Logs

```bash
# All services, follow
docker compose -f deploy/compose/docker-compose.prod.yml --env-file deploy/env/.env.prod logs -f

# Backend only
docker compose ... logs -f backend

# Worker
docker compose ... logs -f worker
```

Backend logs are structured JSON (`structlog`). Each request includes a `request_id` field.

### Admin dashboard

Accessible at `https://admin.hideoutbutler.com`. Protected by:
- HTTP Basic auth (username + bcrypt password)
- TOTP second factor
- IP allowlist (`ADMIN_IP_ALLOWLIST`)

### Resource usage (target VM)

| Service | Memory limit |
|---|---|
| Traefik | 96 MB |
| Postgres | 320 MB |
| Redis | 160 MB |
| Backend | 256 MB |
| Worker | 128 MB |
| Frontend (nginx) | 64 MB |
| Admin | 64 MB |
| **Total** | **~1088 MB** |

On a 1 GB VM, keep the OS footprint low and avoid running other services.

---

## 7. Backup & restore

### Postgres backup

```bash
docker compose ... exec postgres \
  pg_dump -U poe2b poe2b | gzip > poe2b_$(date +%Y%m%d).sql.gz
```

### Restore

```bash
gunzip -c poe2b_20260101.sql.gz | \
  docker compose ... exec -T postgres psql -U poe2b poe2b
```

### What is stored in Postgres

- `users` — account names, preferred league, valuable threshold.
- `user_tokens` — AES-GCM encrypted GGG tokens.
- `snapshots` — JSONB payload + prev_payload for characters, stashes, profile.

Redis data is ephemeral (sessions, cache, rate-limit counters). It does not need to be backed up.

---

## 8. Traefik configuration summary

| Environment | Config file | Provider |
|---|---|---|
| Dev | `deploy/compose/traefik/traefik.dev.yml` | Static file (`dynamic.dev.yml`, HTTP) |
| UAT | `deploy/compose/traefik/traefik.uat.yml` + `dynamic.uat.yml` | Static file, HTTPS + origin cert (no Docker socket) |
| Prod | `deploy/compose/traefik/traefik.prod.yml` + `dynamic.prod.yml` | Docker labels + file TLS (Cloudflare Origin CA) |

Dev uses a static provider to avoid exposing the Docker socket inside the Traefik container.

---

## 9. CI/CD (GitHub Actions)

Workflows in `.github/workflows/`:

| Workflow | Trigger | What it does |
|---|---|---|
| `ci.yml` | push / PR | Lint (ruff, eslint), unit tests (pytest, vitest), dependency audit |

To publish images to GHCR (optional), add a workflow that builds and pushes `ghcr.io/${GITHUB_OWNER}/poe2b-{backend,frontend,admin}:${IMAGE_TAG}` on releases. The prod compose file references these tags.
