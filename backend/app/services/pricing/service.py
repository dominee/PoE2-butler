"""Pricing service: cache-aware read-through lookup and bulk warmer."""

from __future__ import annotations

import asyncio
from collections.abc import Iterable

from app.domain.item import Item
from app.logging import get_logger
from app.services.pricing.cache import PriceCache
from app.services.pricing.matcher import ItemKey, match_item
from app.services.pricing.source import PriceEstimate, PriceSource

log = get_logger("app.services.pricing")


class PricingService:
    def __init__(self, source: PriceSource, cache: PriceCache) -> None:
        self._source = source
        self._cache = cache

    async def price_for(self, league: str, item: Item) -> PriceEstimate | None:
        key = match_item(item)
        return await self._price_by_key(league, key)

    async def price_bulk(
        self, league: str, items: Iterable[Item]
    ) -> dict[str, PriceEstimate | None]:
        """Return ``{item.id: estimate|None}`` for each item."""
        result: dict[str, PriceEstimate | None] = {}
        sem = asyncio.Semaphore(8)

        async def one(item: Item) -> None:
            async with sem:
                result[item.id] = await self.price_for(league, item)

        await asyncio.gather(*(one(i) for i in items))
        return result

    async def warm(self, league: str, items: Iterable[Item]) -> int:
        """Fetch and cache prices for every item. Returns the number priced."""
        priced = 0
        for item in items:
            estimate = await self.price_for(league, item)
            if estimate is not None:
                priced += 1
        return priced

    async def _price_by_key(self, league: str, key: ItemKey) -> PriceEstimate | None:
        cached = await self._cache.get(league, key)
        if cached == "miss":
            return None
        if cached is not None:
            return cached  # type: ignore[return-value]

        estimate = await self._source.lookup(league, key)
        if estimate is None:
            await self._cache.set_miss(league, key)
            return None
        await self._cache.set(league, key, estimate)
        return estimate
