"""Shared pytest fixtures."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("ENVIRONMENT", "test")

# Expose `app_stack` (OAuth + in-memory DB) to other test modules.
pytest_plugins = ("tests.test_auth_flow",)


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    return "asyncio"
