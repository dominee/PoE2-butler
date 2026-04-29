"""Redis state for async price estimate jobs."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel

from app.services.pricing.source import PriceEstimate

JobStatus = Literal["queued", "running", "completed", "failed"]


class PriceJobState(BaseModel):
    status: JobStatus = "queued"
    step: str = ""
    message: str = ""
    result: PriceEstimate | None = None
    error: str | None = None
    user_id: str = ""
    item_id: str = ""
    item_name: str = ""
    league: str = ""
    updated_at: str = ""


def job_key(job_id: str) -> str:
    return f"poe2b:price_job:{job_id}"


def dedup_key(user_id: str, item_id: str, league: str) -> str:
    return f"poe2b:price_dedup:{user_id}:{league}:{item_id}"


async def save_job_state(redis, job_id: str, state: PriceJobState, *, ttl_sec: int = 3600) -> None:
    now = datetime.now(UTC).replace(microsecond=0).isoformat()
    stamped = state.model_copy(update={"updated_at": now})
    await redis.set(job_key(job_id), stamped.model_dump_json(), ex=ttl_sec)


async def load_job_state(redis, job_id: str) -> PriceJobState | None:
    raw = await redis.get(job_key(job_id))
    if not raw:
        return None
    if isinstance(raw, bytes):
        raw = raw.decode()
    try:
        d: dict[str, Any] = json.loads(raw)
        if d.get("result") is not None and isinstance(d["result"], dict):
            d["result"] = PriceEstimate.model_validate(d["result"])
        return PriceJobState.model_validate(d)
    except (json.JSONDecodeError, ValueError, TypeError):
        return None


async def load_redis_inflight_estimate_for_item(
    redis,
    *,
    user_id: str,
    item_id: str,
    league: str,
) -> PriceJobState | None:
    """Resolve a non-terminal job via the estimate dedup slot (Redis only until Postgres upsert)."""
    raw = await redis.get(dedup_key(user_id, item_id, league))
    if not raw:
        return None
    job_id = raw.decode().strip() if isinstance(raw, bytes) else str(raw).strip()
    if not job_id:
        return None
    st = await load_job_state(redis, job_id)
    if st is None:
        return None
    if st.user_id and st.user_id != user_id:
        return None
    if st.status not in ("queued", "running"):
        return None
    return st


async def get_or_set_dedup(redis, user_id: str, item_id: str, league: str, new_job_id: str) -> str:
    """Return an existing in-flight *job_id* (NX miss), or reserve *new_job_id* and return it."""
    k = dedup_key(user_id, item_id, league)
    ok = await redis.set(k, new_job_id, ex=600, nx=True)
    if ok:
        return new_job_id
    v = await redis.get(k)
    if isinstance(v, bytes):
        v = v.decode()
    return str(v).strip() if v else new_job_id
