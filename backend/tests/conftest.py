"""Shared pytest fixtures."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("ENVIRONMENT", "test")

# Expose `app_stack` (OAuth + in-memory DB) to other test modules.
pytest_plugins = ("tests.test_auth_flow",)


@pytest.fixture(autouse=True)
def _reset_db_engine_cache() -> None:
    """Avoid leaking cached async engines between tests."""
    yield
    from app.db import base as db_base

    if hasattr(db_base.get_engine, "cache_clear"):
        db_base.get_engine.cache_clear()
    if hasattr(db_base._session_factory, "cache_clear"):
        db_base._session_factory.cache_clear()


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    return "asyncio"
