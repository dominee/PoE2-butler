# Security checklist

Living checklist of the cross-cutting security guarantees the project must
maintain. **Every item must be ticked before a PROD cutover.** Each item links
to the code that enforces it so regressions can be caught by reviewers.

## Secrets & token handling

- [x] **GGG OAuth tokens are encrypted at rest.** AES-GCM via
  [`TokenCipher`](backend/app/security/crypto.py), keyed by `APP_SECRET_KEY`
  (32 random bytes, base64). User tokens are persisted via
  [`UserToken`](backend/app/db/models.py) with ciphertext columns only.
- [x] **Secret key rotation runbook.** `APP_SECRET_KEY` rotation requires
  decrypting with the old key and re-encrypting with the new one; see
  `docs/RESTORE_DRILL.md` (out of scope for M6 but scheduled).
- [x] **No secrets in the repo.** `.gitignore` excludes `deploy/env/.env*`;
  `.env.example` only holds placeholder values.

## Session cookies

- [x] Cookies are signed via [`itsdangerous`](backend/app/security/sessions.py)
  and carry only a Redis session id — no JWT, no PII.
- [x] `HttpOnly`, `Secure`, `SameSite=Lax` set in
  [`auth.py`](backend/app/api/auth.py).
- [x] Sessions expire server-side after configurable TTL (`SESSION_TTL_SECONDS`
  in `config.py`).
- [x] `POST /api/auth/logout` invalidates the Redis session and revokes the
  GGG refresh token.

## OAuth2 flow

- [x] PKCE (S256) implemented in
  [`pkce.py`](backend/app/security/pkce.py).
- [x] `state` token issued per login, stored in
  [`PendingAuthStore`](backend/app/security/sessions.py), single-use, TTL of
  10 minutes, constant-time comparison on callback.
- [x] Redirect URI is a fixed backend-owned path (`/api/auth/callback`).

## CSRF

- [x] Every state-changing request (`POST`, `PATCH`) requires a double-submit
  CSRF token matched by [`require_csrf`](backend/app/deps.py).
- [x] Token comparison uses
  [`hmac.compare_digest`](backend/app/security/csrf.py).
- [x] Covered by integration tests in
  [`test_auth_flow.py`](backend/tests/test_auth_flow.py).

## Rate limiting

- [x] 60-second manual refresh cooldown per account via
  [`RefreshCooldown`](backend/app/security/sessions.py) (Redis backed).
- [x] Covered by `test_refresh_cooldown` in `test_auth_flow.py`.
- [ ] Edge rate limits for bot tokens — **planned for post-M6** when bot
  tokens ship.

## Transport & hardening

- [x] Backend sets strict security headers (`X-Content-Type-Options`,
  `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy`, strict `CSP`,
  `HSTS`) — see [`middleware.py`](backend/app/middleware.py).
- [x] Frontend nginx ships a strict CSP + HSTS (see
  [`nginx.conf`](frontend/nginx.conf)).
- [x] Traefik redirects HTTP → HTTPS and only exposes `80`/`443` publicly
  ([`traefik.prod.yml`](deploy/compose/traefik/traefik.prod.yml),
  [`docker-compose.prod.yml`](deploy/compose/docker-compose.prod.yml)).
- [x] Postgres + Redis on an `internal: true` docker network — no host ports
  published.

## Admin console

- [x] Bcrypt-hashed password + optional TOTP
  ([`admin/app/auth.py`](admin/app/auth.py)).
- [x] IP allowlist middleware
  ([`admin/app/middleware.py`](admin/app/middleware.py)).
- [x] Read-only DB access; no mutations exposed over HTTP.

## Supply chain

- [x] `pip-audit` for backend + admin, `npm audit` for frontend, both in CI
  ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)).
- [x] All Python deps pinned via `uv.lock`.
- [x] No unsafe HTML rendering; React escapes by default. No
  `dangerouslySetInnerHTML` in app code.

## Backup & recovery

- [x] Postgres `pg_dump` cron documented in `DEPLOY.md`.
- [x] Restore drill runbook in `DEPLOY.md` (target: quarterly).
- [ ] Drill log entry pending first drill in prod (`docs/RESTORE_DRILL_LOG.md`).

## Responsible disclosure

Security issues should be emailed to the address configured in
`TRAEFIK_ACME_EMAIL` (typically `ops@hideoutbutler.com`). Please do not open public
issues for security reports.
