"""Pricing endpoints: bulk price lookup for client-side item lists."""

from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.db.base import get_session
from app.db.models import User
from app.deps import get_current_user, get_pricing_service, get_redis, require_csrf
from app.domain.item import Item
from app.services.price_queue import get_arq_pool
from app.services.pricing.currency_rates import resolve_currency_rates
from app.services.pricing.estimate_persist import load_persisted_estimate
from app.services.pricing.estimate_state import (
    PriceJobState,
    get_or_set_dedup,
    list_inflight_price_jobs_for_user,
    load_job_state,
    load_redis_inflight_estimate_for_item,
    save_job_state,
)
from app.services.pricing.service import PricingService
from app.services.pricing.source import PriceEstimate

router = APIRouter(prefix="/api/pricing", tags=["pricing"])


class CurrencyRatesResponse(BaseModel):
    league: str
    chaos_per_divine: float
    chaos_per_exalted: float
    exalted_per_divine: float | None
    source: str


class PricingRequest(BaseModel):
    league: str
    items: list[Item]


class PricingResponse(BaseModel):
    league: str
    prices: dict[str, PriceEstimate | None]


@router.get("/currency-rates", summary="Divine/Exalted chaos values and ex-per-div for UI")
async def get_currency_rates(
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    league: str = Query(..., min_length=1),
) -> CurrencyRatesResponse:
    _ = user
    data = await resolve_currency_rates(settings, league.strip())
    epd = data["exalted_per_divine"]
    return CurrencyRatesResponse(
        league=str(data["league"]),
        chaos_per_divine=float(data["chaos_per_divine"]),
        chaos_per_exalted=float(data["chaos_per_exalted"]),
        exalted_per_divine=float(epd) if epd is not None else None,
        source=str(data["source"]),
    )


@router.post("/lookup", summary="Bulk price estimate for items")
async def lookup_prices(
    body: PricingRequest,
    user: User = Depends(get_current_user),
    pricing: PricingService = Depends(get_pricing_service),
) -> PricingResponse:
    _ = user  # authenticated-only; we don't filter by user yet
    prices = await pricing.price_bulk(body.league, body.items)
    return PricingResponse(league=body.league, prices=prices)


class PriceEstimateRequest(BaseModel):
    league: str
    item: Item
    tolerance_pct: float | None = Field(default=None, ge=0, le=500)


class PriceEstimateEnqueued(BaseModel):
    job_id: str
    deduped: bool = False


@router.get(
    "/estimate/item",
    summary="Latest persisted hybrid estimate for a stash item (same tolerance as when computed)",
    response_model=None,
)
async def get_persisted_item_estimate(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    redis=Depends(get_redis),
    league: str = Query(..., min_length=1),
    item_id: str = Query(..., min_length=1),
    tolerance_pct: float | None = Query(default=None, ge=0, le=500),
) -> Response:
    tol = float(tolerance_pct if tolerance_pct is not None else user.trade_tolerance_pct)
    st = await load_persisted_estimate(
        session,
        user_id=user.id,
        league=league.strip(),
        item_id=item_id.strip(),
        tolerance_pct=tol,
    )
    if st is not None:
        return JSONResponse(content=st.model_dump(mode="json"))
    inflight = await load_redis_inflight_estimate_for_item(
        redis,
        user_id=str(user.id),
        item_id=item_id.strip(),
        league=league.strip(),
    )
    if inflight is not None:
        return JSONResponse(content=inflight.model_dump(mode="json"))
    return Response(status_code=204)


@router.get("/estimate/{job_id}", summary="Status of a hybrid price estimate job")
async def get_price_estimate_job(
    job_id: str,
    user: User = Depends(get_current_user),
    redis=Depends(get_redis),
) -> PriceJobState:
    st = await load_job_state(redis, job_id)
    if st is None:
        raise HTTPException(status_code=404, detail="job_not_found")
    if st.user_id and st.user_id != str(user.id):
        raise HTTPException(status_code=404, detail="job_not_found")
    return st


@router.post(
    "/estimate",
    summary="Start hybrid price estimate (async; poll GET /estimate/{id})",
    dependencies=[Depends(require_csrf)],
)
async def start_price_estimate(
    body: PriceEstimateRequest,
    user: User = Depends(get_current_user),
    redis=Depends(get_redis),
) -> PriceEstimateEnqueued:
    if not body.league.strip():
        raise HTTPException(status_code=400, detail="league_required")
    new_job = str(uuid.uuid4())
    job_id = await get_or_set_dedup(redis, str(user.id), str(body.item.id), body.league, new_job)
    if job_id != new_job:
        return PriceEstimateEnqueued(job_id=job_id, deduped=True)

    tol = float(
        body.tolerance_pct
        if body.tolerance_pct is not None
        else user.trade_tolerance_pct
    )
    item_dump = body.item.model_dump(mode="json")
    display_name = (body.item.name or body.item.type_line or "").strip()[:200]
    q = PriceJobState(
        user_id=str(user.id),
        item_id=str(body.item.id),
        item_name=display_name,
        league=body.league,
        status="queued",
        message="queued",
    )
    await save_job_state(redis, job_id, q)
    pool = await get_arq_pool()
    await pool.enqueue_job(
        "price_estimate_item",
        job_id,
        str(user.id),
        body.league,
        item_dump,
        tol,
    )
    return PriceEstimateEnqueued(job_id=job_id, deduped=False)


class AppriseQueued(BaseModel):
    ok: bool = True
    league: str


class InflightPriceJobItem(BaseModel):
    item_id: str
    status: Literal["queued", "running"]
    item_name: str = ""
    message: str = ""


class InflightPriceJobsResponse(BaseModel):
    league: str
    items: list[InflightPriceJobItem]


@router.get("/inflight", summary="Queued/running hybrid price jobs for the current user")
async def list_inflight_price_jobs(
    user: User = Depends(get_current_user),
    redis=Depends(get_redis),
    league: str = Query(..., min_length=1),
) -> InflightPriceJobsResponse:
    jobs = await list_inflight_price_jobs_for_user(
        redis, user_id=str(user.id), league=league.strip()
    )
    return InflightPriceJobsResponse(
        league=league.strip(),
        items=[
            InflightPriceJobItem(
                item_id=st.item_id,
                status=st.status,  # type: ignore[arg-type]
                item_name=st.item_name,
                message=st.message,
            )
            for st in jobs
            if st.item_id
        ],
    )


@router.post(
    "/apprise",
    summary="Queue stash hybrid price estimates (missing DB rows first; capped)",
    dependencies=[Depends(require_csrf)],
)
async def apprise_stash_prices(
    user: User = Depends(get_current_user),
    league: str | None = Query(
        default=None,
        description="League id; defaults to the signed-in user's preferred league.",
    ),
) -> AppriseQueued:
    """Enqueue ``backfill_item_price_estimates`` for stash tabs and character gear in ``league``."""
    lg = (league or user.preferred_league or "").strip()
    if not lg:
        raise HTTPException(status_code=400, detail="league_required")
    try:
        pool = await get_arq_pool()
        await pool.enqueue_job("backfill_item_price_estimates", str(user.id), lg, False)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail="queue_unavailable") from exc
    return AppriseQueued(league=lg)
