"""League divine/exalted chaos rates for UI (poe.ninja or config fallbacks)."""

from __future__ import annotations

from app.config import Settings
from app.services.pricing.poe_ninja import PoeNinjaSource


async def resolve_currency_rates(settings: Settings, league: str) -> dict[str, float | str | None]:
    """Return chaos per div/ex and ``exalted_per_divine`` (how many ex for 1 div)."""
    if settings.pricing_source == "poe_ninja":
        src = PoeNinjaSource(settings.pricing_base_url)
        try:
            m = await src.currency_chaos_map(league)
        finally:
            await src.aclose()
        cdiv = m.get("divine orb") or m.get("divine")
        cex = m.get("exalted orb") or m.get("exalted")
        source = "poe_ninja"
    else:
        cdiv, cex = None, None
        source = "config_fallback"
    fd = float(settings.trade_listing_divine_to_chaos)
    fe = float(settings.trade_listing_exalt_to_chaos)
    cdiv = float(cdiv) if cdiv is not None and cdiv > 0 else fd
    cex = float(cex) if cex is not None and cex > 0 else fe
    ex_per_div: float | None = (cdiv / cex) if cdiv > 0 and cex > 0 else None
    return {
        "league": league,
        "chaos_per_divine": cdiv,
        "chaos_per_exalted": cex,
        "exalted_per_divine": ex_per_div,
        "source": source,
    }
