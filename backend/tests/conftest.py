"""Shared pytest fixtures."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("ENVIRONMENT", "test")


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    return "asyncio"
