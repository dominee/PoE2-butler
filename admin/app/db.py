"""Lightweight read-only DB helpers for the admin console.

We intentionally avoid importing the backend's ORM to keep this service a
standalone observability target: pure SQL + asyncpg via SQLAlchemy Core is
enough for the read views we expose.

Dashboard time-window queries use PostgreSQL ``INTERVAL`` syntax; the admin
console expects ``ADMIN_DATABASE_URL`` to point at Postgres (same as prod).
"""

from __future__ import annotations

from functools import lru_cache

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from admin.app.config import get_admin_settings


@lru_cache
def get_engine() -> AsyncEngine:
    return create_async_engine(get_admin_settings().database_url, future=True)


async def count_totals() -> dict[str, int]:
    """Row counts for dashboard headline cards."""
    engine = get_engine()
    async with engine.connect() as conn:
        rows = await conn.execute(
            text(
                "SELECT (SELECT COUNT(*) FROM users) AS users, "
                "(SELECT COUNT(*) FROM snapshots) AS snapshots"
            )
        )
        row = rows.first()
        if row is None:
            return {"users": 0, "snapshots": 0}
        m = dict(row._mapping)
        return {"users": int(m["users"] or 0), "snapshots": int(m["snapshots"] or 0)}


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


async def dashboard_metrics() -> dict:
    """Single round-trip aggregates for the operator dashboard (PostgreSQL)."""
    engine = get_engine()
    async with engine.connect() as conn:
        row = (
            await conn.execute(
                text(
                    "SELECT "
                    "(SELECT COUNT(*) FROM users "
                    " WHERE last_login_at IS NOT NULL "
                    " AND last_login_at >= NOW() - INTERVAL '7 days') AS active_users_7d, "
                    "(SELECT COUNT(*) FROM user_tokens) AS token_rows, "
                    "(SELECT COUNT(*) FROM item_shares WHERE revoked_at IS NULL) AS active_shares, "
                    "(SELECT COUNT(*) FROM snapshots "
                    " WHERE fetched_at >= NOW() - INTERVAL '24 hours') AS snapshots_24h, "
                    "(SELECT MAX(fetched_at) FROM snapshots) AS last_snapshot_at"
                )
            )
        ).first()
        if row is None:
            return {
                "active_users_7d": 0,
                "token_rows": 0,
                "active_shares": 0,
                "snapshots_24h": 0,
                "last_snapshot_at": None,
            }
        m = dict(row._mapping)
        return {
            "active_users_7d": int(m["active_users_7d"] or 0),
            "token_rows": int(m["token_rows"] or 0),
            "active_shares": int(m["active_shares"] or 0),
            "snapshots_24h": int(m["snapshots_24h"] or 0),
            "last_snapshot_at": m["last_snapshot_at"],
        }
