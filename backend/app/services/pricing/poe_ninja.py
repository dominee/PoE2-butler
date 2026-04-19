"""poe.ninja-style price source.

The public poe.ninja API exposes separate endpoints per item type; we fetch
each bucket once per league and index them in-memory.  The overall shape is
close enough between PoE1 and PoE2 community mirrors that swapping the base
URL is enough to target whichever community economy tracker exists for the
current PoE2 league (poe2scout, poe2.ninja, …).  Configure the base URL via
``settings.pricing_base_url``.
"""

from __future__ import annotations

import time
from typing import Any

import httpx

from app.logging import get_logger
from app.services.pricing.matcher import ItemKey
from app.services.pricing.source import PriceEstimate, PriceUnit

log = get_logger("app.services.pricing.poe_ninja")

# Bucket names on poe.ninja. Order matters for lookup precedence (uniques first).
UNIQUE_BUCKETS = [
    "UniqueArmour",
    "UniqueWeapon",
    "UniqueJewel",
    "UniqueAccessory",
    "UniqueFlask",
    "UniqueRelic",
    "UniqueMap",
]
CURRENCY_BUCKETS = ["Currency", "Fragment"]


class PoeNinjaSource:
    name = "poe.ninja"

    def __init__(self, base_url: str, *, client: httpx.AsyncClient | None = None) -> None:
        self._base = base_url.rstrip("/")
        self._client = client or httpx.AsyncClient(timeout=httpx.Timeout(10.0))
        self._cache: dict[str, dict[str, Any]] = {}
        self._cache_ts: dict[str, float] = {}
        self._ttl = 60 * 15

    async def aclose(self) -> None:
        await self._client.aclose()

    async def lookup(self, league: str, key: ItemKey) -> PriceEstimate | None:
        buckets: list[str]
        if key.category == "currency":
            buckets = CURRENCY_BUCKETS
        elif key.category == "unique":
            buckets = UNIQUE_BUCKETS
        else:
            return None

        for bucket in buckets:
            entry = await self._find(league, bucket, key)
            if entry is not None:
                return entry
        return None

    async def _find(self, league: str, bucket: str, key: ItemKey) -> PriceEstimate | None:
        data = await self._fetch_bucket(league, bucket)
        lines = data.get("lines", []) if isinstance(data, dict) else []
        target_name = key.name.lower() if key.name else key.base_type.lower()
        for line in lines:
            name = str(line.get("currencyTypeName") or line.get("name") or "").lower()
            base = str(line.get("baseType") or "").lower()
            if name == target_name or base == key.base_type.lower():
                value = line.get("chaosValue") or line.get("chaosEquivalent")
                if value is None:
                    continue
                return PriceEstimate(
                    value=float(value),
                    unit=PriceUnit.CHAOS,
                    chaos_equiv=float(value),
                    source=self.name,
                    confidence=1.0,
                )
        return None

    async def _fetch_bucket(self, league: str, bucket: str) -> dict[str, Any]:
        cache_key = f"{league}:{bucket}"
        now = time.monotonic()
        if cache_key in self._cache and now - self._cache_ts.get(cache_key, 0.0) < self._ttl:
            return self._cache[cache_key]

        path = "currencyoverview" if bucket in CURRENCY_BUCKETS else "itemoverview"
        url = f"{self._base}/{path}"
        params = {"league": league, "type": bucket}
        try:
            resp = await self._client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPError as exc:
            log.warning("pricing.fetch_failed", bucket=bucket, error=str(exc))
            return {}

        self._cache[cache_key] = data
        self._cache_ts[cache_key] = now
        return data
