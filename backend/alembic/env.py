"""Alembic environment using the app's async engine."""

from __future__ import annotations

import asyncio

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from alembic import context
from app.config import get_settings
from app.db import models  # noqa: F401  -- ensure models are imported for autogenerate
from app.db.base import Base

target_metadata = Base.metadata


def _url() -> str:
    return get_settings().database_url


def run_migrations_offline() -> None:
    context.configure(
        url=_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


async def run_async() -> None:
    engine: AsyncEngine = create_async_engine(_url(), future=True)
    async with engine.connect() as conn:
        await conn.run_sync(do_run_migrations)
    await engine.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
