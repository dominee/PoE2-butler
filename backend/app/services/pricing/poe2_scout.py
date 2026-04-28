"""POE2Scout (or similar) — optional tier-B price source.

A public HTTP contract is not yet wired in this repository. When
``PRICING_SCOUT_BASE_URL`` is empty, :meth:`lookup` always returns ``None``.

See ``docs/pricing_estimates.md`` and https://poe2scout.com/api/swagger for
server-side options; include a stable ``User-Agent`` with contact if you
enable a real URL.
"""

from __future__ import annotations

import httpx

from app.logging import get_logger
from app.services.pricing.matcher import ItemKey
from app.services.pricing.source import PriceEstimate

log = get_logger("app.services.pricing.poe2_scout")


class Poe2ScoutSource:
    name = "poe2scout"

    def __init__(self, base_url: str, *, client: httpx.AsyncClient | None = None) -> None:
        self._base = (base_url or "").strip().rstrip("/")
        self._client = client

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()

    async def lookup(self, league: str, key: ItemKey) -> PriceEstimate | None:
        if not self._base:
            return None
        # Optional future: GET a documented unique/currency path. No default path
        # is hard-coded to avoid calling an incorrect production URL.
        _ = league, key
        log.debug("poe2_scout.skip_not_configured", base=self._base)
        return None
