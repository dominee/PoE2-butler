"""Optional secondary / community price sources (protocol)."""

from __future__ import annotations

from typing import Protocol

from app.services.pricing.matcher import ItemKey
from app.services.pricing.source import PriceEstimate


class SecondaryPriceSource(Protocol):
    name: str

    async def lookup(self, league: str, key: ItemKey) -> PriceEstimate | None: ...
