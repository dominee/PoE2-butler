# backend

FastAPI backend for PoE2 Hideout Butler.

## Local run (without Docker)

```bash
uv sync
uv run uvicorn app.main:app --reload --port 8000
```

## Tests

```bash
uv run pytest
uv run ruff check .
```

See top-level [AGENTS.md](../AGENTS.md) for architecture and conventions.
