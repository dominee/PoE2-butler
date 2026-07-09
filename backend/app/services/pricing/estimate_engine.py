"""Hybrid price estimate: aggregators, optional scout, then GGG trade listings."""

from __future__ import annotations

from app.config import Settings
from app.domain.item import Item, coerce_item_dict
from app.logging import get_logger
from app.services.pricing.estimate_state import PriceJobState, save_job_state
from app.services.pricing.matcher import match_item
from app.services.pricing.poe2_scout import Poe2ScoutSource
from app.services.pricing.poe_ninja import PoeNinjaSource
from app.services.pricing.service import PricingService
from app.services.pricing.source import PriceEstimate, PriceUnit
from app.services.third_party_ratelimit import (
    await_price_estimate_slot,
    release_price_estimate_slot,
)
from app.services.trade_listings import (
    normalize_trade_chaos_map,
    sample_median_listing_chaos,
    trade_currency_chaos_fallback,
    trade_listing_ids_from_search_post,
    trade_search_collect_string_ids,
)
from app.services.trade_relaxation import apply_relaxation_step, stat_filter_drop_indices
from app.services.trade_search_submit import submit_trade_search
from app.services.trade_stat_index import enrich_trade_payload_stat_ids, ensure_trade_stats_index
from app.services.trade_url import build_exact_search_with_stat_filters, stat_filters_for_exact_item

log = get_logger("app.services.pricing.estimate_engine")


def _item_display_name(item: Item) -> str:
    n = (item.name or item.type_line or "").strip()
    return n[:200] if n else ""


def _poe_ninja_from_settings(settings: Settings) -> PoeNinjaSource | None:
    if settings.pricing_source == "poe_ninja":
        return PoeNinjaSource(settings.pricing_base_url)
    return None


async def build_chaos_currency_map(settings: Settings, league: str) -> dict[str, float]:
    base = trade_currency_chaos_fallback(settings)
    poe = _poe_ninja_from_settings(settings)
    if poe is not None and league:
        m = await poe.currency_chaos_map(league)
        await poe.aclose()
        if m:
            base.update(m)
    return normalize_trade_chaos_map(base, settings)


def _value_display_units(
    chaos_equiv: float, chaos_map: dict[str, float]
) -> tuple[float, PriceUnit]:
    div = chaos_map.get("divine orb") or chaos_map.get("divine")
    ex = chaos_map.get("exalted orb") or chaos_map.get("exalted")
    if div and div > 0 and chaos_equiv >= div * 0.3:
        return (chaos_equiv / div, PriceUnit.DIVINE)
    if ex and ex > 0 and chaos_equiv >= ex * 0.2:
        return (chaos_equiv / ex, PriceUnit.EXALTED)
    return (chaos_equiv, PriceUnit.CHAOS)


def _enrich_aggregator(estimate: PriceEstimate, method: str) -> PriceEstimate:
    return estimate.model_copy(
        update={"estimate_method": method, "sample_size": None, "relaxation_steps": None}
    )


async def run_hybrid_price_estimate(  # noqa: PLR0912,PLR0915
    settings: Settings,
    redis,
    user_id: str,
    item: Item,
    league: str,
    tolerance_pct: float,
    *,
    job_id: str,
    price_svc: PricingService,
) -> PriceEstimate | None:
    if not league.strip() or not job_id:
        return None

    waiting = PriceJobState(
        user_id=user_id,
        item_id=str(item.id),
        item_name=_item_display_name(item),
        league=league,
        status="queued",
        message="Waiting for price estimate slot",
    )
    await save_job_state(redis, job_id, waiting)

    slot_token = await await_price_estimate_slot(redis, settings)
    try:
        st = PriceJobState(
            user_id=user_id,
            item_id=str(item.id),
            item_name=_item_display_name(item),
            league=league,
            status="running",
            message="starting",
        )
        await save_job_state(redis, job_id, st)
        key = match_item(item)
        st.status = "running"
        st.step = "aggregators"
        st.message = "Checking economy sources"
        await save_job_state(redis, job_id, st)

        ag = await price_svc.price_for(league, item)
        if ag is not None and key.category not in ("rare", "magic"):
            st.status = "completed"
            st.result = _enrich_aggregator(ag, "aggregator")
            st.message = st.result.source
            await save_job_state(redis, job_id, st)
            return st.result

        scout: Poe2ScoutSource | None = None
        if settings.pricing_scout_base_url:
            scout = Poe2ScoutSource(settings.pricing_scout_base_url)
            s_est = await scout.lookup(league, key)
            await scout.aclose()
            if s_est is not None:
                st.status = "completed"
                st.result = s_est.model_copy(update={"estimate_method": "poe2scout"})
                st.message = "poe2scout"
                await save_job_state(redis, job_id, st)
                return st.result

        if not settings.pricing_trade_estimate_enabled:
            st.status = "completed"
            st.message = "Trade listing estimate disabled"
            st.result = _enrich_aggregator(ag, "aggregator") if ag is not None else None
            await save_job_state(redis, job_id, st)
            return st.result

        return await _run_trade_hybrid_tail(
            settings,
            redis,
            st,
            job_id,
            item,
            league,
            tolerance_pct,
            ag,
            key,
            price_svc,
        )
    finally:
        await release_price_estimate_slot(redis, slot_token)


async def _run_trade_hybrid_tail(  # noqa: PLR0912,PLR0915
    settings: Settings,
    redis,
    st: PriceJobState,
    job_id: str,
    item: Item,
    league: str,
    tolerance_pct: float,
    ag: PriceEstimate | None,
    key,
    price_svc: PricingService,
) -> PriceEstimate | None:
    st.step = "ggg_trade"
    st.message = "Resolving trade stats and sampling listings"
    await save_job_state(redis, job_id, st)
    await ensure_trade_stats_index(settings)
    full = stat_filters_for_exact_item(item, tolerance_pct)
    order = stat_filter_drop_indices(full)
    chaos_map = await build_chaos_currency_map(settings, league)

    chosen_median = 0.0
    chosen_n = 0
    used_steps = 0
    for step in range(0, len(order) + 1):
        sub = apply_relaxation_step(full, step, order)
        b = build_exact_search_with_stat_filters(
            item, sub, tolerance_pct=tolerance_pct, league=league
        )
        pl = b.get("payload")
        if not isinstance(pl, dict):
            continue
        enrich_trade_payload_stat_ids(pl)
        last_total = 0
        for _attempt in range(200):
            sid, post_body, submit_rl, _status_code = await submit_trade_search(
                settings, league, pl, redis=redis
            )
            if submit_rl:
                st.message = "GGG rate limit (trade search) — waiting before retry"
                await save_job_state(redis, job_id, st)
                continue
            if not sid:
                log.info("price_estimate.search_submit_failed", step=step)
                break
            post_ids, post_total = trade_listing_ids_from_search_post(post_body)
            if post_ids:
                total, ids, list_rl = post_total, post_ids, False
            else:
                total, ids, list_rl = await trade_search_collect_string_ids(
                    settings, league, sid, redis=redis
                )
            if list_rl:
                st.message = "GGG rate limit (trade list) — waiting before retry"
                await save_job_state(redis, job_id, st)
                continue
            if not ids:
                break
            med, n, sample_rl = await sample_median_listing_chaos(
                settings,
                league,
                sid,
                chaos_map,
                min_samples=3,
                cap_ids=32,
                redis=redis,
                list_ids=ids,
                robust_median=True,
            )
            if sample_rl:
                st.message = "GGG rate limit (trade fetch) — waiting before retry"
                await save_job_state(redis, job_id, st)
                continue
            if n > 0 and med > 0:
                chosen_median, chosen_n, used_steps = med, n, step
                last_total = total
            break
        if chosen_median > 0 and (
            last_total >= settings.pricing_min_trade_listings
            or chosen_n >= settings.pricing_min_trade_listings
        ):
            break

    if chosen_median > 0:
        v, u = _value_display_units(chosen_median, chaos_map)
        st.status = "completed"
        st.result = PriceEstimate(
            value=round(v, 2),
            unit=u,
            chaos_equiv=round(chosen_median, 2),
            source="ggg_trade2",
            confidence=0.75 if chosen_n < settings.pricing_min_trade_listings else 0.9,
            note="Median of instant-buyout listings (outlier-resistant); indicative only",
            estimate_method="trade_median",
            sample_size=chosen_n,
            relaxation_steps=used_steps,
        )
        st.message = "ok"
        st.error = None
        await save_job_state(redis, job_id, st)
        return st.result

    st.status = "failed" if ag is None else "completed"
    st.error = "no_listings" if ag is None else None
    st.result = _enrich_aggregator(ag, "aggregator") if ag is not None else None
    st.message = "No price found" if ag is None else (st.result.source if st.result else "")
    await save_job_state(redis, job_id, st)
    return st.result


def item_from_payload(d: dict) -> Item:
    return coerce_item_dict(d)
