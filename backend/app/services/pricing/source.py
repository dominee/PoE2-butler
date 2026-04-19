"""Abstract price source interface and data classes."""

from __future__ import annotations

from enum import StrEnum
from typing import Protocol

from pydantic import BaseModel

from app.services.pricing.matcher import ItemKey


class PriceUnit(StrEnum):
    CHAOS = "chaos"
    DIVINE = "divine"
    EXALTED = "exalted"


class PriceEstimate(BaseModel):
    value: float
    unit: PriceUnit = PriceUnit.CHAOS
    chaos_equiv: float
    source: str
    confidence: float = 1.0
    note: str | None = None


class PriceSource(Protocol):
    """Return a :class:`PriceEstimate` for ``key`` or ``None`` if unknown."""

    name: str

    async def lookup(self, league: str, key: ItemKey) -> PriceEstimate | None: ...
