"""Pricing endpoints: bulk price lookup for client-side item lists."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.db.models import User
from app.deps import get_current_user, get_pricing_service
from app.domain.item import Item
from app.services.pricing.service import PricingService
from app.services.pricing.source import PriceEstimate

router = APIRouter(prefix="/api/pricing", tags=["pricing"])


class PricingRequest(BaseModel):
    league: str
    items: list[Item]


class PricingResponse(BaseModel):
    league: str
    prices: dict[str, PriceEstimate | None]


@router.post("/lookup", summary="Bulk price estimate for items")
async def lookup_prices(
    body: PricingRequest,
    user: User = Depends(get_current_user),
    pricing: PricingService = Depends(get_pricing_service),
) -> PricingResponse:
    _ = user  # authenticated-only; we don't filter by user yet
    prices = await pricing.price_bulk(body.league, body.items)
    return PricingResponse(league=body.league, prices=prices)
