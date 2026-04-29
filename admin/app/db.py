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


def _item_ids_from_character_payload(payload: object) -> set[str]:
    if not isinstance(payload, dict):
        return set()
    out: set[str] = set()
    for slot in ("equipment", "items"):
        arr = payload.get(slot)
        if not isinstance(arr, list):
            continue
        for raw in arr:
            if isinstance(raw, dict) and raw.get("id") is not None:
                s = str(raw["id"]).strip()
                if s:
                    out.add(s)
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
