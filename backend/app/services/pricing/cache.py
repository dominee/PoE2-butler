"""Redis cache for price lookups."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from app.services.pricing.matcher import ItemKey
from app.services.pricing.source import PriceEstimate

if TYPE_CHECKING:
    from redis.asyncio import Redis


PRICE_TTL_SECONDS = 900  # 15 minutes — we keep prices warm but rotate often
NEGATIVE_TTL_SECONDS = 600  # misses cached briefly so we don't hammer upstream


class PriceCache:
    """Redis-backed read-through cache for :class:`PriceEstimate`."""

    def __init__(self, redis: Redis, *, prefix: str = "price") -> None:
        self._redis = redis
        self._prefix = prefix

    @staticmethod
    def key(league: str, key: ItemKey) -> str:
        return (f"{league}:{key.category}:{key.base_type}:{key.name}:{key.rarity}").lower()

    async def get(self, league: str, key: ItemKey) -> PriceEstimate | None | str:
        """Return an estimate, ``None`` for cache miss, ``"miss"`` for negative cache."""
        raw = await self._redis.get(f"{self._prefix}:{self.key(league, key)}")
        if raw is None:
            return None
        if raw == "__miss__":
            return "miss"
        return PriceEstimate(**json.loads(raw))

    async def set(self, league: str, key: ItemKey, estimate: PriceEstimate) -> None:
        await self._redis.set(
            f"{self._prefix}:{self.key(league, key)}",
            estimate.model_dump_json(),
            ex=PRICE_TTL_SECONDS,
        )

    async def set_miss(self, league: str, key: ItemKey) -> None:
        await self._redis.set(
            f"{self._prefix}:{self.key(league, key)}",
            "__miss__",
            ex=NEGATIVE_TTL_SECONDS,
        )
