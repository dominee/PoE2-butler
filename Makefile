# PoE2 Hideout Butler — build, run, and test (see also TESTS.md and README.md).
# Requires: Docker with Compose v2, uv, Node 22+ / npm, GNU Make.
#
# Override: make up ENV=deploy/env/.env.e2e
# Optional: E2E_PLAYWRIGHT_BASE_URL, EXTRA_COMPOSE
#

# Non-interactive make/IDEs often have a short PATH. Prepend where Homebrew usually installs `node`/`npm`.
# If you use nvm only, run:  source ~/.nvm/nvm.sh  in that terminal before `make`, or add your Node bin to PATH.
export PATH := /opt/homebrew/bin:/usr/local/bin:$(PATH)

# Docker Compose (dev stack: Traefik, Postgres, Redis, API, Vite, mock-ggg, admin)
COMPOSE_FILE := deploy/compose/docker-compose.dev.yml
ENV         ?= deploy/env/.env.dev
COMPOSE     := docker compose -f $(COMPOSE_FILE) --env-file $(ENV) $(EXTRA_COMPOSE)

# Playwright: browser must reach this host (see TESTS.md, /etc/hosts, Traefik)
E2E_PLAYWRIGHT_BASE_URL ?= http://app.dev.hideoutbutler.com

PY_DIRS := backend admin mock-ggg
FRONTEND  := frontend

# ---------------------------------------------------------------------------
# Default: list targets
# ---------------------------------------------------------------------------

.DEFAULT_GOAL := help

.PHONY: help
help:
	@echo "Build & run (Docker: $(COMPOSE_FILE), env: \$$ENV = $(ENV)):"
	@echo "  make build         Build or rebuild service images"
	@echo "  make up            Build if needed, start in background"
	@echo "  make up-fg         same, foreground (attached logs)"
	@echo "  make down          Stop and remove containers"
	@echo "  make down-v        same, remove named volumes (wipes local DB / redis data in compose)"
	@echo "  make ps            docker compose ps"
	@echo "  make logs s=...    Follow one service, e.g.  make logs s=backend  (omit s for all services)"
	@echo "  make migrate       backend: alembic upgrade head (stack must be up)"
	@echo "  make frontend-build  Vite + tsc production build to frontend/dist/ (on host)"
	@echo ""
	@echo "Dependencies (host, no containers):"
	@echo "  make install-deps  uv sync (all Python trees) + npm in frontend"
	@echo ""
	@echo "Lint, format, types:"
	@echo "  make lint            Ruff (Python) + ESLint (frontend)"
	@echo "  make format          ruff format in backend, admin, mock-ggg"
	@echo "  make typecheck-frontend  npx tsc -b"
	@echo ""
	@echo "Tests (by category; unit tests do not need Docker):"
	@echo "  make test-backend|test-admin|test-mock|test-frontend"
	@echo "  make test            All of the above (incl. lint and tsc for the frontend)"
	@echo "  make test-all-docker Run all tests + security checks in Docker only (no host npm/uv needed)"
	@echo "  make test-e2e        Playwright (dev stack and hostnames must be up; see TESTS.md)"
	@echo "  make playwright-install  npx playwright install (Chromium + system deps, esp. on Linux)"
	@echo ""
	@echo "Other:"
	@echo "  make check           run pytest in backend+admin and vitest in the frontend (fast; use lint first for static checks)"
	@echo "  make clean-frontend  remove $(FRONTEND)/dist"
	@echo "  make clean            remove pycache, pytest, and ruff caches, and dist; keeps .venv and node_modules"
	@echo ""
	@echo "Variables: ENV, E2E_PLAYWRIGHT_BASE_URL, EXTRA_COMPOSE, PATH (if npm is still not found)"

# ---------------------------------------------------------------------------
# Build & run
# ---------------------------------------------------------------------------

.PHONY: build up up-fg down down-v ps logs migrate frontend-build

build:
	$(COMPOSE) build

up: build
	$(COMPOSE) up -d

up-fg: build
	$(COMPOSE) up

down:
	$(COMPOSE) down

down-v:
	$(COMPOSE) down -v

ps:
	$(COMPOSE) ps

# Examples:  make logs  |  make logs s=backend
logs:
	$(COMPOSE) logs -f --tail=200 $(s)

migrate:
	$(COMPOSE) exec -T backend alembic upgrade head

frontend-build: require-npm
	cd $(FRONTEND) && npm run build

# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------

.PHONY: install-deps install-deps-py install-deps-js require-npm
install-deps: install-deps-py install-deps-js

install-deps-py:
	@set -e; for d in $(PY_DIRS); do (cd $$d && uv sync); done

install-deps-js: require-npm
	cd $(FRONTEND) && ( [ -f package-lock.json ] && npm ci || npm install )

# `npm` must be on PATH for these recipes (export PATH in this Makefile + require-npm).
.PHONY: require-npm
require-npm:
	@command -v npm >/dev/null 2>&1 || ( \
		echo "npm: command not found. Install Node 22+ or extend PATH."; \
		echo "  e.g. Homebrew: ensure /opt/homebrew/bin is in PATH, or: export PATH=\"/opt/homebrew/bin:$$PATH\""; \
		echo "  nvm:      source \"$$HOME/.nvm/nvm.sh\"  then run make again in that terminal."; \
		exit 1; \
	)

# If node_modules is missing, run npm (used by lint, test-frontend, check, playwright-install, test-e2e)
.PHONY: ensure-node-modules
ensure-node-modules: require-npm
	@cd $(FRONTEND) && ( [ -d node_modules ] || ( [ -f package-lock.json ] && npm ci || npm install ) )

# ---------------------------------------------------------------------------
# Lint & format
# ---------------------------------------------------------------------------

.PHONY: lint typecheck-frontend format lint-py lint-frontend
lint: lint-py lint-frontend
lint-py:
	@set -e; for d in $(PY_DIRS); do (cd $$d && uv sync && uv run ruff check .); done
lint-frontend: ensure-node-modules
	cd $(FRONTEND) && npm run lint
typecheck-frontend: ensure-node-modules
	cd $(FRONTEND) && npx tsc -b
format:
	@set -e; for d in $(PY_DIRS); do (cd $$d && uv sync && uv run ruff format .); done

# ---------------------------------------------------------------------------
# Unit / integration tests
# ---------------------------------------------------------------------------

.PHONY: test test-backend test-admin test-mock test-frontend check test-all-docker
test: test-backend test-admin test-mock test-frontend

test-backend:
	cd backend && uv sync && uv run ruff check . && uv run pytest -ra

test-admin:
	cd admin && uv sync && uv run ruff check . && uv run pytest -ra

test-mock:
	cd mock-ggg && uv sync && uv run ruff check .

test-frontend: ensure-node-modules
	cd $(FRONTEND) && npm run lint && npx tsc -b && npm test

# Quicker gate: pytest + vitest (run  make install-deps  once for a new clone; does not re-run ruff or eslint)
check: ensure-node-modules
	cd backend && uv run pytest -ra
	cd admin && uv run pytest -ra
	cd $(FRONTEND) && npm test

# Full host-tool-independent gate:
# - Runs backend/admin/mock/frontend checks in Docker containers.
# - Runs security scans used by security-review.yml in Docker as visibility-only
#   (scan findings do not fail this target yet, matching current CI policy).
test-all-docker:
	@echo "==> [docker] backend lint + tests"
	docker run --rm -v "$(PWD):/work" -w /work/backend ghcr.io/astral-sh/uv:python3.12-bookworm \
		sh -lc "uv sync --frozen || uv sync; uv run ruff check .; uv run pytest -ra"
	@echo "==> [docker] admin lint + tests"
	docker run --rm -v "$(PWD):/work" -w /work/admin ghcr.io/astral-sh/uv:python3.12-bookworm \
		sh -lc "uv sync --frozen || uv sync; uv run ruff check .; uv run pytest -ra"
	@echo "==> [docker] mock-ggg lint"
	docker run --rm -v "$(PWD):/work" -w /work/mock-ggg ghcr.io/astral-sh/uv:python3.12-bookworm \
		sh -lc "uv sync --frozen || uv sync; uv run ruff check ."
	@echo "==> [docker] frontend lint + typecheck + unit tests"
	docker run --rm -v "$(PWD):/work" -w /work/frontend node:22 \
		sh -lc "npm install && npm run lint && npx tsc -b && npm test"
	@echo "==> [docker] security scans (visibility-only)"
	docker run --rm -v "$(PWD):/src" -w /src semgrep/semgrep:latest \
		semgrep scan --config auto --error --json --output /tmp/semgrep.json || true
	docker run --rm -v "$(PWD):/repo" zricethezav/gitleaks:latest \
		detect --source /repo --report-format json --report-path /tmp/gitleaks.json || true
	docker run --rm -v "$(PWD):/src" -w /src ghcr.io/google/osv-scanner:latest \
		scan source -r . --format json --output-file /tmp/osv.json || true
	docker run --rm -v "$(PWD):/work" -w /work/backend ghcr.io/astral-sh/uv:python3.12-bookworm \
		sh -lc "uv export --frozen --format requirements.txt --no-emit-project --output-file /tmp/requirements.backend.txt; uv run --with pip-audit pip-audit -r /tmp/requirements.backend.txt || true"
	docker run --rm -v "$(PWD):/work" -w /work/admin ghcr.io/astral-sh/uv:python3.12-bookworm \
		sh -lc "uv export --frozen --format requirements.txt --no-emit-project --output-file /tmp/requirements.admin.txt; uv run --with pip-audit pip-audit -r /tmp/requirements.admin.txt || true"
	docker run --rm -v "$(PWD):/work" -w /work/mock-ggg ghcr.io/astral-sh/uv:python3.12-bookworm \
		sh -lc "uv export --frozen --format requirements.txt --no-emit-project --output-file /tmp/requirements.mock-ggg.txt; uv run --with pip-audit pip-audit -r /tmp/requirements.mock-ggg.txt || true"
	docker run --rm -v "$(PWD):/work" -w /work/frontend node:22 \
		sh -lc "npm audit --omit=dev --audit-level=high || true"
	@echo "==> [docker] done"

# ---------------------------------------------------------------------------
# E2E
# ---------------------------------------------------------------------------

.PHONY: test-e2e playwright-install
playwright-install: ensure-node-modules
	cd $(FRONTEND) && npx playwright install --with-deps chromium

test-e2e: require-npm
	@if [ ! -f "$(ENV)" ]; then echo "Missing $(ENV) — see TESTS.md and README (copy from deploy/env/.env.example)."; exit 1; fi
	@if [ ! -d $(FRONTEND)/node_modules ]; then echo "Run: make install-deps  (or make install-deps-js)."; exit 1; fi
	cd $(FRONTEND) && PLAYWRIGHT_BASE_URL=$(E2E_PLAYWRIGHT_BASE_URL) npm run test:e2e

# ---------------------------------------------------------------------------
# Clean
# ---------------------------------------------------------------------------

.PHONY: clean clean-frontend
clean-frontend:
	rm -rf $(FRONTEND)/dist
clean: clean-frontend
	@for d in $(PY_DIRS); do \
		find "$$d" -type d \( -name __pycache__ -o -name .pytest_cache -o -name .ruff_cache \) -print0 2>/dev/null | xargs -0 rm -rf; \
		true; \
	done
	@echo "Removed Python __pycache__ / .pytest_cache / .ruff_cache under $(PY_DIRS) and $(FRONTEND)/dist. Kept .venv, node_modules."
