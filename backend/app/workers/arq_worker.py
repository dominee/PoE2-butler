"""Arq worker: background snapshot jobs.

Entry point for the ``arq`` CLI::

    uv run arq app.workers.arq_worker.WorkerSettings

**Jobs (INSTRUCTIONS: queue + pricing background work)**:

* ``refresh_user`` — re-fetch GGG snapshots for a user.
* ``warm_prices`` — pre-fill pricing cache (poe.ninja or static) with
  :func:`app.services.third_party_ratelimit.throttle` around hot loops.
* ``backfill_item_price_estimates`` — hybrid estimates (stash-only or stash+gear);
  missing DB rows first, then oldest ``computed_at``, capped by ``pricing_backfill_max_items``.
  Writes each capped item to Redis as ``queued`` before work starts so admin **Price queue**
  shows the full batch. Triggered from **Apprise** (``POST /api/pricing/apprise``). Uses a
  **longer arq timeout** (see ``arq_backfill_job_timeout_seconds``).
* ``refresh_trade_filter_catalog`` — download/cache PoE2 trade filter metadata
  (used by :mod:`app.services.trade_stat_catalog`).

``arq`` uses Redis; per-vendor throttling uses separate Redis keys (see
``third_party_ratelimit``) — not a second message broker.
"""

from __future__ import annotations

import uuid

from arq.connections import RedisSettings
from arq.worker import func
from redis.asyncio import Redis

from app.clients.ggg import GGGClient
from app.config import get_settings
from app.db.base import _session_factory
from app.db.models import SnapshotKind, User
from app.domain.character import collect_character_items
from app.domain.item import Item, parse_item
from app.logging import configure_logging, get_logger
from app.security.crypto import TokenCipher
from app.services.pricing import PriceCache
from app.services.pricing.estimate_engine import (
    _item_display_name,
    item_from_payload,
    run_hybrid_price_estimate,
)
from app.services.pricing.estimate_persist import upsert_price_job_state
from app.services.pricing.estimate_state import PriceJobState, bind_job_dedup, save_job_state
from app.services.pricing.poe_ninja import PoeNinjaSource
from app.services.pricing.service import PricingService
from app.services.pricing.static import StaticPriceSource
from app.services.snapshot import (
    delete_character_snapshots,
    get_latest_snapshot,
    refresh_user_snapshot,
)
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
            await delete_character_snapshots(session, user.id)
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
                items = [parse_item(i) for i in collect_character_items(payload)]
                priced += await pricing.warm(league, items)
        return {"ok": True, "priced": priced}
    finally:
        await redis.aclose()
        if hasattr(source, "aclose"):
            await source.aclose()  # type: ignore[attr-defined]


async def price_estimate_item(
    ctx: dict,
    job_id: str,
    user_id: str,
    league: str,
    item_dict: dict,
    tolerance_pct: float,
) -> dict:
    """Background hybrid price estimate (see :doc:`docs/pricing_estimates.md`)."""
    log = get_logger("app.workers.price_estimate_item")
    settings = get_settings()
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    source = (
        PoeNinjaSource(settings.pricing_base_url)
        if settings.pricing_source == "poe_ninja"
        else StaticPriceSource()
    )
    cache = PriceCache(redis)
    pricing = PricingService(source, cache)
    try:
        item = item_from_payload(item_dict)
        out = await run_hybrid_price_estimate(
            settings,
            redis,
            user_id,
            item,
            league,
            float(tolerance_pct),
            job_id=job_id,
            price_svc=pricing,
        )
        return {"ok": True, "chaos": out.chaos_equiv if out else None}
    except Exception as exc:  # noqa: BLE001
        log.warning("price_estimate_item.failed", error=str(exc), job_id=job_id)

        display = ""
        n = item_dict.get("name")
        t = item_dict.get("type_line")
        if isinstance(n, str) and n.strip():
            display = n.strip()[:200]
        elif isinstance(t, str) and t.strip():
            display = t.strip()[:200]
        st = PriceJobState(
            user_id=user_id,
            item_id=str(item_dict.get("id", "")),
            item_name=display,
            league=league,
            status="failed",
            error=str(exc)[:200],
            message="error",
        )
        await save_job_state(redis, job_id, st)
        return {"ok": False, "error": str(exc)}
    finally:
        try:
            from app.services.pricing.estimate_state import load_job_state

            st_final = await load_job_state(redis, job_id)
            if st_final is not None and st_final.status in ("completed", "failed"):
                iid = str(item_dict.get("id", "")).strip()
                if iid:
                    factory = _session_factory()
                    async with factory() as session:
                        await upsert_price_job_state(
                            session,
                            user_id=uuid.UUID(user_id),
                            league=league,
                            item_id=iid,
                            tolerance_pct=float(tolerance_pct),
                            job=st_final,
                        )
                        await session.commit()
        except Exception as persist_exc:  # noqa: BLE001
            log.warning("price_estimate_item.persist_failed", error=str(persist_exc), job_id=job_id)
        if hasattr(source, "aclose"):
            await source.aclose()  # type: ignore[attr-defined]
        await redis.aclose()


async def backfill_item_price_estimates(
    ctx: dict,
    user_id: str,
    league: str,
    stash_only: bool = False,
    character_name: str | None = None,
) -> dict:
    """Persist hybrid estimates: missing rows first, then oldest ``computed_at``.

    When ``character_name`` is set, only that character's gear is considered (Apprise).
    When ``stash_only`` is True, only stash tab items are considered.
    Otherwise stash tabs and all equipped character items are included.
    """
    log = get_logger("app.workers.backfill_item_price_estimates")
    settings = get_settings()
    league = league.strip()
    if not league:
        return {"ok": False, "reason": "empty_league"}
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    source = (
        PoeNinjaSource(settings.pricing_base_url)
        if settings.pricing_source == "poe_ninja"
        else StaticPriceSource()
    )
    cache = PriceCache(redis)
    pricing = PricingService(source, cache)
    done = 0
    try:
        from app.services.pricing.estimate_persist import list_estimate_meta_for_league
        from app.services.pricing.estimate_state import load_job_state

        factory = _session_factory()
        async with factory() as session:
            user = await session.get(User, uuid.UUID(user_id))
            if user is None:
                return {"ok": False, "reason": "missing_user"}
            tol = float(user.trade_tolerance_pct)
            meta = await list_estimate_meta_for_league(session, user_id=user.id, league=league)
            char_key = (character_name or "").strip() or None
            if char_key:
                raws = await _collect_character_gear_raws(session, user.id, char_key)
            elif stash_only:
                raws = await _collect_stash_raws(session, user.id, league)
            else:
                raws = await _collect_stash_and_gear_raws(session, user.id, league)
            log.info(
                "backfill_item.start",
                user_id=user_id,
                league=league,
                stash_only=stash_only,
                character=char_key,
                candidates=len(raws),
            )
            missing = [(iid, raw) for iid, raw in raws if iid not in meta]
            had = [(iid, raw) for iid, raw in raws if iid in meta]
            had.sort(key=lambda t: meta[t[0]])
            ordered = missing + had
            cap = max(0, settings.pricing_backfill_max_items)
            todo: list[tuple[str, dict, str, Item]] = []
            for iid, raw in ordered[:cap]:
                try:
                    item = parse_item(raw)
                except Exception:
                    log.info("backfill_item.parse_skip", item_id=iid)
                    continue
                todo.append((iid, raw, str(uuid.uuid4()), item))

            n_batch = len(todo)
            for idx, (iid, _raw, job_id, item) in enumerate(todo):
                q = PriceJobState(
                    user_id=str(user_id),
                    item_id=iid,
                    item_name=_item_display_name(item),
                    league=league,
                    status="queued",
                    message=f"queued ({idx + 1}/{n_batch})",
                )
                await save_job_state(redis, job_id, q)
                await bind_job_dedup(redis, str(user_id), iid, league, job_id)

            for iid, _raw, job_id, item in todo:
                await throttle(redis, KEY_POE_NINJA)
                try:
                    await run_hybrid_price_estimate(
                        settings,
                        redis,
                        user_id,
                        item,
                        league,
                        tol,
                        job_id=job_id,
                        price_svc=pricing,
                    )
                    st = await load_job_state(redis, job_id)
                    if st is not None:
                        await upsert_price_job_state(
                            session,
                            user_id=user.id,
                            league=league,
                            item_id=iid,
                            tolerance_pct=tol,
                            job=st,
                        )
                        await session.commit()
                        done += 1
                except Exception as exc:  # noqa: BLE001
                    log.info("backfill_item.skip", item_id=iid, error=str(exc)[:120])
                    await session.rollback()
        return {"ok": True, "estimated": done}
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


async def _collect_stash_raws(session, user_id: uuid.UUID, league: str) -> list[tuple[str, dict]]:
    """Stash tab items only, stable tab order."""
    out: list[tuple[str, dict]] = []
    seen: set[str] = set()

    def push(raw: object) -> None:
        if not isinstance(raw, dict):
            return
        iid = str(raw.get("id") or "").strip()
        if not iid or iid in seen:
            return
        seen.add(iid)
        out.append((iid, raw))

    list_snap = await get_latest_snapshot(session, user_id, SnapshotKind.STASH_LIST, key=league)
    if list_snap is None:
        return []
    for tab in list_snap.payload.get("tabs", []) or []:
        tid = tab.get("id")
        if not tid:
            continue
        snap = await get_latest_snapshot(
            session, user_id, SnapshotKind.STASH_TAB, key=f"{league}:{tid}"
        )
        if snap is None:
            continue
        for raw in snap.payload.get("items", []) or []:
            push(raw)
    return out


async def _collect_character_gear_raws(
    session, user_id: uuid.UUID, character_name: str
) -> list[tuple[str, dict]]:
    """Equipped gear, gems, and inventory for one character snapshot."""
    snap = await get_latest_snapshot(
        session, user_id, SnapshotKind.CHARACTER, key=character_name
    )
    if snap is None:
        return []
    out: list[tuple[str, dict]] = []
    seen: set[str] = set()

    def push(raw: object) -> None:
        if not isinstance(raw, dict):
            return
        iid = str(raw.get("id") or "").strip()
        if not iid or iid in seen:
            return
        seen.add(iid)
        out.append((iid, raw))

    for raw in collect_character_items(snap.payload):
        push(raw)
    return out


async def _collect_stash_and_gear_raws(
    session, user_id: uuid.UUID, league: str
) -> list[tuple[str, dict]]:
    """Stable order: stash tabs as listed, then character equipment."""
    out = await _collect_stash_raws(session, user_id, league)
    seen = {iid for iid, _ in out}

    def push(raw: object) -> None:
        if not isinstance(raw, dict):
            return
        iid = str(raw.get("id") or "").strip()
        if not iid or iid in seen:
            return
        seen.add(iid)
        out.append((iid, raw))

    for payload in await _all_character_snapshots(session, user_id):
        for raw in collect_character_items(payload):
            push(raw)
    return out


async def startup(ctx: dict) -> None:
    configure_logging(get_settings().log_level)
    get_logger("app.workers").info("worker.start")


async def shutdown(ctx: dict) -> None:
    get_logger("app.workers").info("worker.stop")


class WorkerSettings:
    functions = [
        refresh_user,
        warm_prices,
        price_estimate_item,
        func(
            backfill_item_price_estimates,
            timeout=get_settings().arq_backfill_job_timeout_seconds,
        ),
        refresh_trade_filter_catalog,
    ]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    max_jobs = get_settings().arq_max_jobs
    job_timeout = get_settings().arq_job_timeout_seconds
