"""Arq worker: background snapshot jobs.

Entry point for the ``arq`` CLI::

    uv run arq app.workers.arq_worker.WorkerSettings

**Jobs (INSTRUCTIONS: queue + pricing background work)**:

* ``refresh_user`` — re-fetch GGG snapshots for a user.
* ``warm_prices`` — pre-fill pricing cache (poe.ninja or static) with
  :func:`app.services.third_party_ratelimit.throttle` around hot loops.
* ``refresh_trade_filter_catalog`` — download/cache PoE2 trade filter metadata
  (used by :mod:`app.services.trade_stat_catalog`).

``arq`` uses Redis; per-vendor throttling uses separate Redis keys (see
``third_party_ratelimit``) — not a second message broker.
"""

from __future__ import annotations

import uuid

from arq.connections import RedisSettings
from redis.asyncio import Redis

from app.clients.ggg import GGGClient
from app.config import get_settings
from app.db.base import _session_factory
from app.db.models import SnapshotKind, User
from app.domain.item import parse_item
from app.logging import configure_logging, get_logger
from app.security.crypto import TokenCipher
from app.services.pricing import PriceCache
from app.services.pricing.poe_ninja import PoeNinjaSource
from app.services.pricing.service import PricingService
from app.services.pricing.static import StaticPriceSource
from app.services.snapshot import get_latest_snapshot, refresh_user_snapshot
from app.services.third_party_ratelimit import KEY_POE_NINJA, throttle


async def refresh_user(ctx: dict, user_id: str) -> dict:
    log = get_logger("app.workers.refresh_user")
    settings = get_settings()
    cipher = TokenCipher(settings)
    ggg = GGGClient(settings)
    try:
        factory = _session_factory()
        async with factory() as session:
            user = await session.get(User, uuid.UUID(user_id))
            if user is None:
                log.warning("refresh_user.missing_user", user_id=user_id)
                return {"ok": False, "reason": "missing_user"}
            outcome = await refresh_user_snapshot(
                session=session, user=user, ggg=ggg, cipher=cipher
            )
            await session.commit()
            return {
                "ok": True,
                "profile": outcome.profile,
                "leagues": outcome.leagues,
                "characters": outcome.characters,
                "errors": outcome.errors or [],
            }
    finally:
        await ggg.aclose()


async def warm_prices(ctx: dict, user_id: str, league: str) -> dict:
    """Pre-populate the pricing cache for a user's current equipment + stashes."""
    log = get_logger("app.workers.warm_prices")
    settings = get_settings()
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    source = (
        PoeNinjaSource(settings.pricing_base_url)
        if settings.pricing_source == "poe_ninja"
        else StaticPriceSource()
    )
    cache = PriceCache(redis)
    pricing = PricingService(source, cache)
    await throttle(redis, KEY_POE_NINJA)

    priced = 0
    try:
        factory = _session_factory()
        async with factory() as session:
            user = await session.get(User, uuid.UUID(user_id))
            if user is None:
                return {"ok": False, "reason": "missing_user"}

            list_snap = await get_latest_snapshot(
                session, user.id, SnapshotKind.STASH_LIST, key=league
            )
            if list_snap is None:
                log.info("warm_prices.no_stash_list", league=league)
                return {"ok": True, "priced": 0}

            tab_ids = [t.get("id") for t in list_snap.payload.get("tabs", []) if t.get("id")]
            for tab_id in tab_ids:
                await throttle(redis, KEY_POE_NINJA)
                snap = await get_latest_snapshot(
                    session, user.id, SnapshotKind.STASH_TAB, key=f"{league}:{tab_id}"
                )
                if snap is None:
                    continue
                items = [parse_item(i) for i in snap.payload.get("items", [])]
                priced += await pricing.warm(league, items)

            char_snaps = await _all_character_snapshots(session, user.id)
            for payload in char_snaps:
                await throttle(redis, KEY_POE_NINJA)
                items = [parse_item(i) for i in payload.get("equipment", [])]
                priced += await pricing.warm(league, items)
        return {"ok": True, "priced": priced}
    finally:
        await redis.aclose()
        if hasattr(source, "aclose"):
            await source.aclose()  # type: ignore[attr-defined]


async def refresh_trade_filter_catalog(ctx: dict) -> dict:
    """Background refresh of GGG trade filter / stat metadata (see trade_stat_catalog)."""
    from app.services import trade_stat_catalog as tsc

    settings = get_settings()
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        n = await tsc.refresh_if_stale(redis, settings)
        return {"ok": True, "stat_entries": n}
    except Exception as exc:  # noqa: BLE001
        get_logger("app.workers.refresh_trade_filter_catalog").warning(
            "refresh_failed", error=str(exc)
        )
        return {"ok": False, "error": str(exc)}
    finally:
        await redis.aclose()


async def _all_character_snapshots(session, user_id):
    from sqlalchemy import select

    from app.db.models import Snapshot

    stmt = (
        select(Snapshot)
        .where(Snapshot.user_id == user_id)
        .where(Snapshot.kind == SnapshotKind.CHARACTER)
    )
    res = await session.execute(stmt)
    return [s.payload for s in res.scalars().all()]


async def startup(ctx: dict) -> None:
    configure_logging(get_settings().log_level)
    get_logger("app.workers").info("worker.start")


async def shutdown(ctx: dict) -> None:
    get_logger("app.workers").info("worker.stop")


class WorkerSettings:
    functions = [refresh_user, warm_prices, refresh_trade_filter_catalog]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    max_jobs = 4
