"""Static price source.

Useful for local dev when no community tracker is available yet, and for
hermetic tests.  Shape mirrors :class:`PoeNinjaSource` so it can be swapped
via :mod:`app.deps`.
"""

from __future__ import annotations

from app.services.pricing.matcher import ItemKey
from app.services.pricing.source import PriceEstimate, PriceUnit

# A tiny, deliberately conservative catalogue. Values here exist so that the
# pricing pipeline is testable end-to-end; production deployments are expected
# to configure :class:`PoeNinjaSource` instead.
DEFAULT_CATALOGUE: dict[str, dict[str, float]] = {
    "currency": {
        "chaos orb": 1.0,
        "divine orb": 180.0,
        "exalted orb": 80.0,
        "mirror of kalandra": 10000.0,
    },
    "unique": {
        "headhunter": 2500.0,
        "mageblood": 3000.0,
    },
}


class StaticPriceSource:
    name = "static"

    def __init__(self, catalogue: dict[str, dict[str, float]] | None = None) -> None:
        self._catalogue = catalogue or DEFAULT_CATALOGUE

    async def lookup(self, league: str, key: ItemKey) -> PriceEstimate | None:
        bucket = self._catalogue.get(key.category)
        if bucket is None:
            return None
        needle = (key.name or key.base_type).lower()
        value = bucket.get(needle)
        if value is None:
            return None
        return PriceEstimate(
            value=value,
            unit=PriceUnit.CHAOS,
            chaos_equiv=value,
            source=self.name,
            confidence=0.75,
            note="static catalogue" if value else None,
        )
