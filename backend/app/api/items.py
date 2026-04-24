"""Item utilities: PoE2-style text for clipboard (same domain as ``item_text``)."""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends
from pydantic import BaseModel

from app.db.models import User
from app.deps import get_current_user
from app.domain.item import Item
from app.domain.item_text import format_item_text

router = APIRouter(prefix="/api/items", tags=["items"])


class ItemTextRequest(BaseModel):
    item: Item


class ItemTextResponse(BaseModel):
    text: str


@router.post(
    "/item-text",
    response_model=ItemTextResponse,
    summary="Format item as PoE2-style text (for in-game / Discord paste)",
)
async def post_item_text(
    body: ItemTextRequest = Body(...),
    _user: User = Depends(get_current_user),
) -> ItemTextResponse:
    return ItemTextResponse(text=format_item_text(body.item))
