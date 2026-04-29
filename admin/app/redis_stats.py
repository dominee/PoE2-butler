"""Redis and queue statistics helpers for the admin console."""

from __future__ import annotations

import json
import pickle
import time
from collections import Counter
from functools import lru_cache
from typing import Any

import httpx
from redis.asyncio import Redis

from admin.app.config import get_admin_settings

# arq.constants (admin does not depend on arq; keep in sync with worker's arq version)
ARQ_QUEUE_ZSET = "arq:queue"
ARQ_IN_PROGRESS_PREFIX = "arq:in-progress:"
ARQ_IN_PROGRESS_GLOB = "arq:in-progress:*"
ARQ_JOB_KEY_PREFIX = "arq:job:"


@lru_cache
def get_redis() -> Redis:
    return Redis.from_url(get_admin_settings().redis_url, decode_responses=True)


@lru_cache
def get_redis_raw() -> Redis:
    """Binary-safe client for arq's pickled ``arq:job:*`` payloads (no ``decode_responses``)."""
    return Redis.from_url(get_admin_settings().redis_url, decode_responses=False)


async def redis_summary() -> dict:
    redis = get_redis()
    info = await redis.info(section="memory")
    info_cpu = await redis.info(section="clients")
    info_stats = await redis.info(section="stats")
    key_count = await redis.dbsize()
    return {
        "key_count": key_count,
        "used_memory_human": info.get("used_memory_human"),
        "used_memory_peak_human": info.get("used_memory_peak_human"),
        "maxmemory_human": info.get("maxmemory_human"),
        "connected_clients": info_cpu.get("connected_clients"),
        "evicted_keys": info_stats.get("evicted_keys"),
        "expired_keys": info_stats.get("expired_keys"),
    }


async def _count_keys_by_scan(redis: Redis, pattern: str) -> int:
    """Count keys matching ``pattern`` (SCAN; safe for large DBs vs KEYS)."""
    n = 0
    cur = 0
    while True:
        cur, keys = await redis.scan(cursor=cur, match=pattern, count=300)
        n += len(keys)
        if cur == 0:
            break
    return n


async def queue_summary() -> dict:
    """Report arq queue stats (zset length + in-progress key count).

    arq stores one Redis string key per running job: ``arq:in-progress:{job_id}``,
    not a set named ``arq:in-progress`` (older docs / examples were misleading).
    """
    redis = get_redis()
    queued = await redis.zcard(ARQ_QUEUE_ZSET)
    in_progress = await _count_keys_by_scan(redis, ARQ_IN_PROGRESS_GLOB)
    return {"queued": queued, "in_progress": in_progress}


def _unpickle_arq_job_function(blob: bytes | None) -> str | None:
    """Read arq's default job blob (``{'f': function_name, ...}``) when pickle succeeds."""
    if not blob:
        return None
    try:
        d = pickle.loads(bytes(blob))
    except (TypeError, pickle.PickleError, ValueError, EOFError, IndexError, AttributeError):
        return None
    if not isinstance(d, dict) or "f" not in d:
        return None
    return str(d["f"])


def _as_job_id_b(member: bytes | str | bytearray | memoryview) -> bytes:
    if isinstance(member, (bytes, bytearray)):
        return bytes(member)
    if isinstance(member, memoryview):
        return member.tobytes()
    return str(member).encode()


async def arq_job_function_breakdown(
    *,
    max_queued: int = 50,
    max_in_progress: int = 50,
) -> dict[str, Any]:
    """Count arq jobs by function name in the queue and in-progress (best-effort via pickle)."""
    r = get_redis_raw()
    q_queued: Counter[str] = Counter()
    q_ip: Counter[str] = Counter()
    fail_q = 0
    fail_ip = 0
    try:
        for jid in await r.zrange(ARQ_QUEUE_ZSET.encode(), 0, max(0, max_queued - 1)):
            jid_b = _as_job_id_b(jid)
            blob = await r.get(ARQ_JOB_KEY_PREFIX.encode() + jid_b)
            fn = _unpickle_arq_job_function(blob)
            if fn is None:
                fail_q += 1
            else:
                q_queued[fn] += 1
    except (TypeError, OSError, ValueError, ConnectionError):
        return {
            "queued_by_function": {},
            "in_progress_by_function": {},
            "unpickle_failed_queued": 0,
            "unpickle_failed_in_progress": 0,
            "unpickle_note": "Could not read arq queue (Redis error).",
        }

    prefix_b = ARQ_IN_PROGRESS_PREFIX.encode()
    inprog_ids: list[bytes] = []
    try:
        cur = 0
        while len(inprog_ids) < max(0, max_in_progress):
            cur, keys = await r.scan(cursor=cur, match=ARQ_IN_PROGRESS_GLOB.encode(), count=200)
            for k in keys:
                if len(inprog_ids) >= max_in_progress:
                    break
                kb = _as_job_id_b(k)
                if kb.startswith(prefix_b):
                    jid = kb[len(prefix_b) :]
                    if jid:
                        inprog_ids.append(jid)
            if cur == 0:
                break
    except (TypeError, OSError, ValueError, ConnectionError):
        inprog_ids = []

    for jid_b in inprog_ids:
        try:
            blob = await r.get(ARQ_JOB_KEY_PREFIX.encode() + jid_b)
        except (TypeError, OSError, ValueError):
            fail_ip += 1
            continue
        fn = _unpickle_arq_job_function(blob)
        if fn is None:
            fail_ip += 1
        else:
            q_ip[fn] += 1

    success_q = int(sum(q_queued.values()))
    success_ip = int(sum(q_ip.values()))
    note: str | None = None
    if fail_q + fail_ip and success_q + success_ip == 0 and (fail_q or fail_ip):
        note = (
            "Could not decode job blobs (unpickle). Often a Python/env mismatch, "
            "or jobs were serialized with a custom serializer on the worker."
        )
    elif fail_q or fail_ip:
        note = f"{fail_q + fail_ip} job id(s) could not be read (missing key or unpickle)."

    return {
        "queued_by_function": dict(sorted(q_queued.items(), key=lambda x: (-x[1], x[0]))),
        "in_progress_by_function": dict(sorted(q_ip.items(), key=lambda x: (-x[1], x[0]))),
        "unpickle_failed_queued": fail_q,
        "unpickle_failed_in_progress": fail_ip,
        "unpickle_note": note,
    }


async def price_cache_summary() -> dict:
    """Count price keys and sample a few for display."""
    redis = get_redis()
    cursor = 0
    total = 0
    sample: list[str] = []
    while True:
        cursor, keys = await redis.scan(cursor=cursor, match="price:*", count=200)
        total += len(keys)
        if len(sample) < 10:
            sample.extend(keys[: 10 - len(sample)])
        if cursor == 0:
            break
    return {"key_count": total, "sample": sample}


# Throttle "next" keys for third_party_ratelimit (vendor + ":next") and GGG global trade lock.
_THROTTLE_TOKENS: tuple[tuple[str, str], ...] = (
    ("ggg_trade2_lock", "tp3:ggg_trade:lock"),
    ("poe_ninja", "tp3:poe_ninja:next"),
    ("ggg_trade_data", "tp3:ggg_trade_data:next"),
    ("ggg_trade_fetch", "tp3:ggg_trade_fetch:next"),
    ("generic", "tp3:generic:next"),
)

_VALID_JOB_STATUS = frozenset({"queued", "running", "completed", "failed"})


def _decode_json_value(raw: Any) -> dict[str, Any] | None:
    if not raw:
        return None
    try:
        if isinstance(raw, str):
            d = json.loads(raw)
        elif isinstance(raw, (bytes, bytearray)):
            d = json.loads(raw.decode())
        else:
            d = json.loads(str(raw))
    except (TypeError, json.JSONDecodeError, ValueError, UnicodeError):
        return None
    return d if isinstance(d, dict) else None


def _chaos_equiv(res: Any) -> float | None:
    if not isinstance(res, dict) or res.get("chaos_equiv") is None:
        return None
    try:
        return float(res["chaos_equiv"])
    except (TypeError, ValueError):
        return None


def _price_job_sample_row(redis_key: str, d: dict[str, Any]) -> dict[str, Any]:
    st = d.get("status")
    st_display: str = st if isinstance(st, str) and st in _VALID_JOB_STATUS else "unknown"
    res = d.get("result")
    err = d.get("error")
    item_id = str(d.get("item_id") or "")
    name_raw = d.get("item_name")
    if isinstance(name_raw, str) and name_raw.strip():
        item_label = name_raw.strip()[:120]
    else:
        item_label = (item_id[:20] + "…") if len(item_id) > 22 else item_id
    jid = redis_key.split(":", 2)[-1] if isinstance(redis_key, str) else str(redis_key)
    chaos = _chaos_equiv(res)
    e_short = None
    if err is not None:
        es = str(err)
        e_short = es[:240] + ("…" if len(es) > 240 else "")
    upd = d.get("updated_at")
    updated_display = str(upd).strip() if isinstance(upd, str) and upd.strip() else None
    return {
        "job_id": (jid[:8] + "…") if len(jid) > 12 else jid,
        "job_id_full": jid,
        "status": st_display,
        "league": str(d.get("league") or ""),
        "item_label": item_label,
        "item_id": item_id,
        "user_id": str(d.get("user_id") or "")[:8] or "—",
        "step": str(d.get("step") or "")[:100],
        "message": str(d.get("message") or "")[:160],
        "chaos_equiv": chaos,
        "error": e_short,
        "updated_at": updated_display,
    }


def _order_price_jobs(j: dict[str, Any]) -> tuple[int, str]:
    s = j.get("status")
    sk = s if isinstance(s, str) else ""
    order = {"running": 0, "queued": 1, "failed": 2, "completed": 3}
    o = order.get(sk, 4)
    return o, str(j.get("job_id_full", ""))


async def _dedup_key_count(redis) -> int:
    n = 0
    cur = 0
    while True:
        cur, keys = await redis.scan(
            cursor=cur,
            match="poe2b:price_dedup:*",
            count=300,
        )
        n += len(keys)
        if cur == 0:
            return n


async def _throttle_slot_snapshot(redis) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for name, tkey in _THROTTLE_TOKENS:
        pttl = await redis.pttl(tkey)
        pttl_i = -2 if pttl is None else int(pttl)
        active = pttl_i > 0
        out.append(
            {
                "name": name,
                "key": tkey,
                "active": active,
                "pttl_ms": max(0, pttl_i) if pttl_i > 0 else 0,
            }
        )
    return out


async def _scan_price_job_keys(
    redis, max_job_keys: int
) -> tuple[dict[str, int], list[dict[str, Any]], int, bool]:
    by_status: dict[str, int] = {
        "queued": 0,
        "running": 0,
        "completed": 0,
        "failed": 0,
        "unknown": 0,
    }
    jobs: list[dict[str, Any]] = []
    partial = False
    scanned = 0
    cursor: int = 0
    while True:
        cursor, keys = await redis.scan(
            cursor=cursor,
            match="poe2b:price_job:*",
            count=400,
        )
        for k in keys:
            scanned += 1
            if scanned > max_job_keys:
                partial = True
                break
            d = _decode_json_value(await redis.get(k))
            if not d:
                by_status["unknown"] += 1
                continue
            st = d.get("status")
            if st in _VALID_JOB_STATUS:
                by_status[st] += 1
            else:
                by_status["unknown"] += 1
            jobs.append(_price_job_sample_row(k, d))
        if partial:
            break
        if cursor == 0:
            break
    return by_status, jobs, scanned, partial


async def price_estimate_observability(
    max_job_keys: int = 4000,
) -> dict[str, Any]:
    """Surface Redis state for background hybrid price estimate jobs and related throttles."""
    redis = get_redis()
    by_status, jobs, scanned, partial = await _scan_price_job_keys(redis, max_job_keys)
    jobs.sort(key=_order_price_jobs)
    sample = jobs[:32]
    dedup = await _dedup_key_count(redis)
    in_flight = by_status["queued"] + by_status["running"]
    return {
        "scanned": scanned,
        "partial_scan": partial,
        "dedup_keys": dedup,
        "in_flight_states": in_flight,
        "by_status": by_status,
        "sample": sample,
        "throttle_slots": await _throttle_slot_snapshot(redis),
    }


def parse_health_body(status_code: int, text: str) -> dict[str, Any]:
    out: dict[str, Any] = {"status_code": status_code, "version": None, "status": None}
    if status_code != 200:
        return out
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, TypeError, ValueError):
        return out
    if isinstance(data, dict):
        if "version" in data:
            out["version"] = data.get("version")
        if "status" in data:
            out["status"] = data.get("status")
    return out


async def backend_health() -> dict[str, dict[str, Any]]:
    """Ping the backend's /healthz and /readyz; include latency and JSON fields when present."""
    settings = get_admin_settings()
    result: dict[str, dict[str, Any]] = {}
    async with httpx.AsyncClient(base_url=settings.backend_base_url, timeout=3.0) as client:
        for path in ("/healthz", "/readyz"):
            t0 = time.perf_counter()
            try:
                resp = await client.get(path)
                elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 2)
                parsed = parse_health_body(resp.status_code, resp.text)
                result[path] = {
                    "status_code": resp.status_code,
                    "latency_ms": elapsed_ms,
                    "version": parsed.get("version"),
                    "body_status": parsed.get("status"),
                    "error": None,
                }
            except httpx.HTTPError as exc:
                elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 2)
                result[path] = {
                    "status_code": None,
                    "latency_ms": elapsed_ms,
                    "version": None,
                    "body_status": None,
                    "error": str(exc),
                }
    return result


def probe_ok(probe: dict[str, Any]) -> bool:
    code = probe.get("status_code")
    return code == 200 and probe.get("error") is None
