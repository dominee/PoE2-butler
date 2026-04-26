"""In-memory index of PoE2 trade stat ids from GGG ``/api/trade2/data/stats``.

Used to attach ``id`` to stat filters built from item mod lines so the trade
site receives filters beyond the small bundled template map.
"""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any

import httpx

from app.config import Settings
from app.logging import get_logger
from app.services.trade_stat_catalog import (
    _BUCKET_STAT_PREFIX,
    bundled_trade_stat_id,
    trade_search_user_agent,
)

log = get_logger("app.services.trade_stat_index")

_WS = re.compile(r"\s+")

_stats_lock = asyncio.Lock()
_stats_ready = False
# (ggg_id_prefix, normalized_stat_text) -> full stat id, e.g. explicit.stat_3299347043
_by_prefix_norm: dict[tuple[str, str], str] = {}


def _normalize_stat_text(text: str) -> str:
    """Match GGG stat ``text`` fields to our ``parse_mod_line`` templates."""
    s = _WS.sub(" ", str(text).replace("\n", " ")).strip()
    while s.startswith("+"):
        s = s[1:].lstrip()
    return s


def _stat_id_prefix(stat_id: str) -> str:
    """``explicit.stat_123`` → ``explicit``; ``pseudo.pseudo_total_life`` → ``pseudo``."""
    return stat_id.split(".", 1)[0]


def _bucket_to_stat_prefixes(bucket: str) -> list[str]:
    """Prefixes to try on the trade index (crafted bench mods use ``explicit`` ids)."""
    mapped = _BUCKET_STAT_PREFIX.get(bucket, bucket)
    if bucket == "crafted":
        return ["explicit", "crafted"]
    return [mapped]


async def ensure_trade_stats_index(settings: Settings) -> None:
    """Load stat metadata once per process (empty index on failure)."""
    global _stats_ready, _by_prefix_norm
    if _stats_ready:
        return
    async with _stats_lock:
        if _stats_ready:
            return
        url = settings.trade_stats_data_url
        merged: dict[tuple[str, str], str] = {}
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                r = await client.get(
                    url,
                    headers={
                        "User-Agent": trade_search_user_agent(settings),
                        "Accept": "application/json",
                    },
                )
            if r.status_code != 200 or not r.text:
                log.warning(
                    "trade_stats_index.fetch_failed",
                    url=url,
                    status_code=getattr(r, "status_code", None),
                )
            else:
                data = r.json()
                for grp in data.get("result") or []:
                    if not isinstance(grp, dict):
                        continue
                    for ent in grp.get("entries") or []:
                        if not isinstance(ent, dict):
                            continue
                        sid = ent.get("id")
                        text = ent.get("text")
                        if not isinstance(sid, str) or not isinstance(text, str):
                            continue
                        pfx = _stat_id_prefix(sid)
                        nt = _normalize_stat_text(text)
                        if not nt:
                            continue
                        key = (pfx, nt)
                        if key not in merged:
                            merged[key] = sid
        except (json.JSONDecodeError, httpx.HTTPError, OSError, TypeError) as exc:
            log.warning("trade_stats_index.load_error", url=url, error=str(exc))
        _by_prefix_norm = merged
        _stats_ready = True


def lookup_trade_stat_id(bucket: str, template: str) -> str | None:
    """Resolve trade stat id for a mod bucket + ``#`` template string."""
    nt = _normalize_stat_text(template)
    if not nt:
        return bundled_trade_stat_id(bucket, template)
    for pfx in _bucket_to_stat_prefixes(bucket):
        sid = _by_prefix_norm.get((pfx, nt))
        if sid:
            return sid
    return bundled_trade_stat_id(bucket, template)


def enrich_trade_payload_stat_ids(payload: dict[str, Any]) -> None:
    """Fill ``id`` on numeric stat filters using the loaded index + bundled map."""
    q = payload.get("query")
    if not isinstance(q, dict):
        return
    stats = q.get("stats")
    if not isinstance(stats, list):
        return
    for block in stats:
        if not isinstance(block, dict):
            continue
        filters = block.get("filters")
        if not isinstance(filters, list):
            continue
        for row in filters:
            if not isinstance(row, dict):
                continue
            if "value" not in row:
                continue
            bucket = str(row.get("bucket") or "explicit")
            template = str(row.get("template") or "")
            if not template:
                continue
            rid = lookup_trade_stat_id(bucket, template)
            if rid:
                row["id"] = rid


def reset_trade_stats_index_for_tests() -> None:
    """Clear cache (tests only)."""
    global _stats_ready, _by_prefix_norm
    _stats_ready = False
    _by_prefix_norm = {}
