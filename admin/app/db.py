"""Lightweight read-only DB helpers for the admin console.

We intentionally avoid importing the backend's ORM to keep this service a
standalone observability target: pure SQL + asyncpg via SQLAlchemy Core is
enough for the read views we expose.

Dashboard time-window queries use PostgreSQL ``INTERVAL`` syntax; the admin
console expects ``ADMIN_DATABASE_URL`` to point at Postgres (same as prod).
"""

from __future__ import annotations

import uuid
from functools import lru_cache
from typing import Any

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


async def list_users(limit: int = 100, query: str | None = None) -> list[dict]:
    engine = get_engine()
    q = (query or "").strip()
    async with engine.connect() as conn:
        if q:
            rows = await conn.execute(
                text(
                    "SELECT id, ggg_account_name, realm, preferred_league, "
                    "trade_tolerance_pct, valuable_threshold_chaos, "
                    "created_at, last_login_at, last_refreshed_at "
                    "FROM users "
                    "WHERE ggg_account_name ILIKE :pat OR CAST(id AS text) = :exact "
                    "ORDER BY created_at DESC LIMIT :limit"
                ),
                {"pat": f"%{q}%", "exact": q, "limit": limit},
            )
        else:
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


def _item_id_from_raw(raw: dict) -> str | None:
    inner = raw.get("itemData")
    for source in (raw, inner if isinstance(inner, dict) else None):
        if isinstance(source, dict):
            iid = source.get("id")
            if iid is not None:
                s = str(iid).strip()
                if s:
                    return s
    return None


def _collect_character_items(payload: dict) -> list[dict]:
    """Flatten gear rows from a character snapshot (PoE2 / mock shapes)."""
    out: list[dict] = []
    seen: set[str] = set()

    def add(raw: object) -> None:
        if not isinstance(raw, dict):
            return
        iid = _item_id_from_raw(raw)
        if iid:
            if iid in seen:
                return
            seen.add(iid)
        out.append(raw)

    for raw in payload.get("items") or []:
        add(raw)
    char = payload.get("character")
    if isinstance(char, dict):
        for key in ("equipment", "inventory", "rucksack", "jewels"):
            for raw in char.get(key) or []:
                add(raw)
    return out


def _item_ids_from_character_payload(payload: object) -> set[str]:
    if not isinstance(payload, dict):
        return set()
    out: set[str] = set()
    for raw in _collect_character_items(payload):
        iid = _item_id_from_raw(raw)
        if iid:
            out.add(iid)
    return out


def _character_profile_label(payload: object, fallback_key: str) -> str:
    if not isinstance(payload, dict):
        return fallback_key or "—"
    ch = payload.get("character")
    if isinstance(ch, dict):
        n = str(ch.get("name") or "").strip()
        cl = str(ch.get("class") or "").strip()
        lv = ch.get("level")
        if n:
            bits = [n]
            if cl:
                bits.append(cl)
            if lv is not None:
                try:
                    bits.append(f"Lv.{int(lv)}")
                except (TypeError, ValueError):
                    bits.append(f"Lv.{lv}")
            return " · ".join(bits)
    return (fallback_key or "").strip() or "—"


async def enrich_price_queue_rows(rows: list[dict]) -> None:
    """Add ``account`` (GGG name) and ``character_profile`` using Postgres snapshots."""
    if not rows:
        return

    uids: dict[str, str] = {}
    for r in rows:
        u = str(r.get("user_id") or "").strip()
        if not u:
            continue
        try:
            uids[u] = str(uuid.UUID(u))
        except ValueError:
            continue

    engine = get_engine()
    async with engine.connect() as conn:
        user_names: dict[str, str] = {}
        char_rows: dict[str, list[tuple[str, dict]]] = {}
        for uid_key, uid_val in uids.items():
            urow = (
                await conn.execute(
                    text("SELECT ggg_account_name FROM users WHERE id = CAST(:id AS uuid)"),
                    {"id": uid_val},
                )
            ).first()
            user_names[uid_key] = str(urow._mapping["ggg_account_name"]) if urow else "—"

            sres = await conn.execute(
                text(
                    "SELECT key, payload FROM snapshots "
                    "WHERE user_id = CAST(:id AS uuid) AND kind = 'character'"
                ),
                {"id": uid_val},
            )
            lst: list[tuple[str, dict]] = []
            for srow in sres.mappings():
                p = srow["payload"]
                pl = p if isinstance(p, dict) else {}
                lst.append((str(srow["key"] or ""), pl))
            char_rows[uid_key] = lst

    for r in rows:
        uid = str(r.get("user_id") or "").strip()
        r["account"] = user_names.get(uid, "—")
        iid = str(r.get("item_id") or "").strip()
        prof: str | None = None
        for _key, payload in char_rows.get(uid, []):
            if iid and iid in _item_ids_from_character_payload(payload):
                prof = _character_profile_label(payload, _key)
                break
        r["character_profile"] = prof if prof else "— (stash or unknown)"


async def get_user_by_id(user_id: str) -> dict | None:
    engine = get_engine()
    async with engine.connect() as conn:
        row = (
            await conn.execute(
                text(
                    "SELECT id, ggg_account_name, ggg_uuid, realm, preferred_league, "
                    "trade_tolerance_pct, valuable_threshold_chaos, "
                    "created_at, last_login_at, last_refreshed_at "
                    "FROM users WHERE id = CAST(:id AS uuid)"
                ),
                {"id": user_id},
            )
        ).first()
        return dict(row._mapping) if row else None


async def get_user_token_meta(user_id: str) -> dict | None:
    engine = get_engine()
    async with engine.connect() as conn:
        row = (
            await conn.execute(
                text(
                    "SELECT scope, expires_at, updated_at "
                    "FROM user_tokens WHERE user_id = CAST(:id AS uuid)"
                ),
                {"id": user_id},
            )
        ).first()
        return dict(row._mapping) if row else None


async def count_user_snapshots_by_kind(user_id: str) -> list[dict]:
    engine = get_engine()
    async with engine.connect() as conn:
        rows = await conn.execute(
            text(
                "SELECT kind, COUNT(*) AS n FROM snapshots "
                "WHERE user_id = CAST(:id AS uuid) GROUP BY kind ORDER BY kind"
            ),
            {"id": user_id},
        )
        return [dict(row._mapping) for row in rows]


async def list_user_snapshots(user_id: str, limit: int = 30) -> list[dict]:
    engine = get_engine()
    async with engine.connect() as conn:
        rows = await conn.execute(
            text(
                "SELECT id, kind, key, fetched_at FROM snapshots "
                "WHERE user_id = CAST(:id AS uuid) "
                "ORDER BY fetched_at DESC LIMIT :limit"
            ),
            {"id": user_id, "limit": limit},
        )
        return [dict(row._mapping) for row in rows]


async def list_user_price_estimates(user_id: str, limit: int = 20) -> list[dict]:
    engine = get_engine()
    async with engine.connect() as conn:
        rows = await conn.execute(
            text(
                "SELECT league, item_id, item_name, status, error, computed_at "
                "FROM item_price_estimates "
                "WHERE user_id = CAST(:id AS uuid) "
                "ORDER BY computed_at DESC NULLS LAST LIMIT :limit"
            ),
            {"id": user_id, "limit": limit},
        )
        return [dict(row._mapping) for row in rows]


async def list_user_shares(user_id: str, limit: int = 20) -> list[dict]:
    engine = get_engine()
    async with engine.connect() as conn:
        rows = await conn.execute(
            text(
                "SELECT id, league, created_at, revoked_at "
                "FROM item_shares "
                "WHERE user_id = CAST(:id AS uuid) "
                "ORDER BY created_at DESC LIMIT :limit"
            ),
            {"id": user_id, "limit": limit},
        )
        return [dict(row._mapping) for row in rows]


async def count_character_history(user_id: str) -> int:
    engine = get_engine()
    async with engine.connect() as conn:
        row = (
            await conn.execute(
                text(
                    "SELECT COUNT(*) AS n FROM character_snapshot_history "
                    "WHERE user_id = CAST(:id AS uuid)"
                ),
                {"id": user_id},
            )
        ).first()
        return int(row._mapping["n"]) if row else 0


async def user_headline_stats() -> dict[str, int]:
    """Headline user counts for the Users dashboard (PostgreSQL)."""
    engine = get_engine()
    async with engine.connect() as conn:
        row = (
            await conn.execute(
                text(
                    "SELECT "
                    "(SELECT COUNT(*) FROM users) AS total_users, "
                    "(SELECT COUNT(*) FROM users "
                    " WHERE last_refreshed_at >= NOW() - INTERVAL '30 days') AS active_30d, "
                    "(SELECT COUNT(*) FROM users "
                    " WHERE last_login_at IS NULL "
                    " OR last_login_at < NOW() - INTERVAL '30 days') AS not_logged_in_30d, "
                    "(SELECT COUNT(*) FROM users "
                    " WHERE last_refreshed_at IS NULL) AS never_refreshed, "
                    "(SELECT COUNT(*) FROM users WHERE last_login_at IS NULL) AS never_logged_in"
                )
            )
        ).first()
        if row is None:
            return {
                "total_users": 0,
                "active_30d": 0,
                "inactive_30d": 0,
                "not_logged_in_30d": 0,
                "never_refreshed": 0,
                "never_logged_in": 0,
            }
        m = dict(row._mapping)
        total = int(m["total_users"] or 0)
        active = int(m["active_30d"] or 0)
        return {
            "total_users": total,
            "active_30d": active,
            "inactive_30d": max(0, total - active),
            "not_logged_in_30d": int(m["not_logged_in_30d"] or 0),
            "never_refreshed": int(m["never_refreshed"] or 0),
            "never_logged_in": int(m["never_logged_in"] or 0),
        }


async def _counts_by_day(
    sql: str,
    *,
    days: int,
    value_key: str = "n",
) -> list[dict[str, Any]]:
    engine = get_engine()
    async with engine.connect() as conn:
        rows = await conn.execute(text(sql), {"days": days})
        out: list[dict[str, Any]] = []
        for row in rows:
            mapping = dict(row._mapping)
            mapping[value_key] = int(mapping[value_key] or 0)
            out.append(mapping)
        return out


async def user_signups_by_day(days: int = 90) -> list[dict[str, Any]]:
    return await _counts_by_day(
        "SELECT (created_at AT TIME ZONE 'UTC')::date AS day, COUNT(*) AS n "
        "FROM users "
        "WHERE created_at >= NOW() - CAST(:days AS integer) * INTERVAL '1 day' "
        "GROUP BY day ORDER BY day",
        days=days,
    )


async def users_before_window(days: int) -> int:
    engine = get_engine()
    async with engine.connect() as conn:
        row = (
            await conn.execute(
                text(
                    "SELECT COUNT(*) AS n FROM users "
                    "WHERE created_at < NOW() - CAST(:days AS integer) * INTERVAL '1 day'"
                ),
                {"days": days},
            )
        ).first()
        return int(row._mapping["n"]) if row else 0


async def user_refresh_distinct_by_day(days: int = 90) -> list[dict[str, Any]]:
    return await _counts_by_day(
        "SELECT (created_at AT TIME ZONE 'UTC')::date AS day, "
        "COUNT(DISTINCT user_id) AS n "
        "FROM user_activity_events "
        "WHERE event_type = 'refresh' "
        "AND created_at >= NOW() - CAST(:days AS integer) * INTERVAL '1 day' "
        "GROUP BY day ORDER BY day",
        days=days,
    )


async def user_refresh_events_by_day(days: int = 90) -> list[dict[str, Any]]:
    return await _counts_by_day(
        "SELECT (created_at AT TIME ZONE 'UTC')::date AS day, COUNT(*) AS n "
        "FROM user_activity_events "
        "WHERE event_type = 'refresh' "
        "AND created_at >= NOW() - CAST(:days AS integer) * INTERVAL '1 day' "
        "GROUP BY day ORDER BY day",
        days=days,
    )


async def user_login_distinct_by_day(days: int = 90) -> list[dict[str, Any]]:
    return await _counts_by_day(
        "SELECT (created_at AT TIME ZONE 'UTC')::date AS day, "
        "COUNT(DISTINCT user_id) AS n "
        "FROM user_activity_events "
        "WHERE event_type = 'login' "
        "AND created_at >= NOW() - CAST(:days AS integer) * INTERVAL '1 day' "
        "GROUP BY day ORDER BY day",
        days=days,
    )


async def character_history_by_day(days: int = 90) -> list[dict[str, Any]]:
    return await _counts_by_day(
        "SELECT (fetched_at AT TIME ZONE 'UTC')::date AS day, COUNT(*) AS n "
        "FROM character_snapshot_history "
        "WHERE fetched_at >= NOW() - CAST(:days AS integer) * INTERVAL '1 day' "
        "GROUP BY day ORDER BY day",
        days=days,
    )


async def price_estimates_by_day(days: int = 90) -> list[dict[str, Any]]:
    return await _counts_by_day(
        "SELECT (computed_at AT TIME ZONE 'UTC')::date AS day, COUNT(*) AS n "
        "FROM item_price_estimates "
        "WHERE computed_at >= NOW() - CAST(:days AS integer) * INTERVAL '1 day' "
        "GROUP BY day ORDER BY day",
        days=days,
    )


async def shares_created_by_day(days: int = 90) -> list[dict[str, Any]]:
    return await _counts_by_day(
        "SELECT day, SUM(n) AS n FROM ( "
        "  SELECT (created_at AT TIME ZONE 'UTC')::date AS day, COUNT(*) AS n "
        "  FROM item_shares "
        "  WHERE created_at >= NOW() - CAST(:days AS integer) * INTERVAL '1 day' "
        "  GROUP BY day "
        "  UNION ALL "
        "  SELECT (created_at AT TIME ZONE 'UTC')::date AS day, COUNT(*) AS n "
        "  FROM character_shares "
        "  WHERE created_at >= NOW() - CAST(:days AS integer) * INTERVAL '1 day' "
        "  GROUP BY day "
        ") combined GROUP BY day ORDER BY day",
        days=days,
    )


async def users_by_league(limit: int = 12) -> list[dict[str, Any]]:
    engine = get_engine()
    async with engine.connect() as conn:
        rows = await conn.execute(
            text(
                "SELECT COALESCE(NULLIF(TRIM(preferred_league), ''), '(none)') AS league, "
                "COUNT(*) AS n "
                "FROM users "
                "GROUP BY league "
                "ORDER BY n DESC, league "
                "LIMIT :limit"
            ),
            {"limit": limit},
        )
        return [dict(row._mapping) for row in rows]

