"""Postgres persistence for completed hybrid price estimate jobs."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ItemPriceEstimate
from app.services.pricing.estimate_state import PriceJobState
from app.services.pricing.source import PriceEstimate

_TOL_EPS = 1e-3


def job_state_to_row_fields(job: PriceJobState, tolerance_pct: float) -> dict[str, Any]:
    result_json = None
    if job.result is not None:
        result_json = job.result.model_dump(mode="json")
    return {
        "tolerance_pct": float(tolerance_pct),
        "item_name": (job.item_name or "")[:200],
        "status": job.status,
        "message": (job.message or "")[:500] if job.message else None,
        "error": (job.error or "")[:500] if job.error else None,
        "result_json": result_json,
    }


async def upsert_price_job_state(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    league: str,
    item_id: str,
    tolerance_pct: float,
    job: PriceJobState,
) -> None:
    """Store terminal ``completed`` / ``failed`` hybrid estimate for reload after app restart."""
    if job.status not in ("completed", "failed"):
        return
    if not item_id.strip():
        return
    fields = job_state_to_row_fields(job, tolerance_pct)
    stmt = select(ItemPriceEstimate).where(
        ItemPriceEstimate.user_id == user_id,
        ItemPriceEstimate.league == league,
        ItemPriceEstimate.item_id == item_id,
    )
    row = (await session.execute(stmt)).scalar_one_or_none()
    now = datetime.now(UTC)
    if row is None:
        session.add(
            ItemPriceEstimate(
                user_id=user_id,
                league=league[:200],
                item_id=item_id[:128],
                computed_at=now,
                **fields,
            )
        )
    else:
        for k, v in fields.items():
            setattr(row, k, v)
        row.computed_at = now


def row_to_price_job_state(row: ItemPriceEstimate) -> PriceJobState:
    result: PriceEstimate | None = None
    if row.result_json:
        result = PriceEstimate.model_validate(row.result_json)
    return PriceJobState(
        status=row.status,  # type: ignore[arg-type]
        step="",
        message=row.message or "",
        result=result,
        error=row.error,
        user_id=str(row.user_id),
        item_id=row.item_id,
        item_name=row.item_name,
        league=row.league,
        updated_at=row.computed_at.isoformat(),
    )


async def load_persisted_estimate(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    league: str,
    item_id: str,
    tolerance_pct: float,
) -> PriceJobState | None:
    stmt = select(ItemPriceEstimate).where(
        ItemPriceEstimate.user_id == user_id,
        ItemPriceEstimate.league == league,
        ItemPriceEstimate.item_id == item_id,
    )
    row = (await session.execute(stmt)).scalar_one_or_none()
    if row is None:
        return None
    if abs(float(row.tolerance_pct) - float(tolerance_pct)) > _TOL_EPS:
        return None
    return row_to_price_job_state(row)


async def list_estimate_meta_for_league(
    session: AsyncSession, *, user_id: uuid.UUID, league: str
) -> dict[str, datetime]:
    """Map ``item_id`` → ``computed_at`` for prioritizing backfill (missing vs stale)."""
    stmt = select(ItemPriceEstimate.item_id, ItemPriceEstimate.computed_at).where(
        ItemPriceEstimate.user_id == user_id,
        ItemPriceEstimate.league == league,
    )
    rows = (await session.execute(stmt)).all()
    return {str(r[0]): r[1] for r in rows if r[0]}
