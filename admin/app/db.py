"""Lightweight read-only DB helpers for the admin console.

We intentionally avoid importing the backend's ORM to keep this service a
standalone observability target: pure SQL + asyncpg via SQLAlchemy Core is
enough for the read views we expose.
"""

from __future__ import annotations

from functools import lru_cache

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from admin.app.config import get_admin_settings


@lru_cache
def get_engine() -> AsyncEngine:
    return create_async_engine(get_admin_settings().database_url, future=True)


async def list_users(limit: int = 100) -> list[dict]:
    engine = get_engine()
    async with engine.connect() as conn:
        rows = await conn.execute(
            text(
                "SELECT id, ggg_account_name, realm, preferred_league, "
                "trade_tolerance_pct, valuable_threshold_chaos, "
                "created_at, last_login_at, last_refreshed_at "
                "FROM users ORDER BY created_at DESC LIMIT :limit"
            ),
            {"limit": limit},
        )
        return [dict(row._mapping) for row in rows]


async def count_snapshots_by_kind() -> list[dict]:
    engine = get_engine()
    async with engine.connect() as conn:
        rows = await conn.execute(
            text("SELECT kind, COUNT(*) AS n FROM snapshots GROUP BY kind ORDER BY kind")
        )
        return [dict(row._mapping) for row in rows]


async def recent_snapshots(limit: int = 50) -> list[dict]:
    engine = get_engine()
    async with engine.connect() as conn:
        rows = await conn.execute(
            text(
                "SELECT s.id, s.kind, s.key, s.fetched_at, u.ggg_account_name "
                "FROM snapshots s "
                "JOIN users u ON u.id = s.user_id "
                "ORDER BY s.fetched_at DESC LIMIT :limit"
            ),
            {"limit": limit},
        )
        return [dict(row._mapping) for row in rows]
