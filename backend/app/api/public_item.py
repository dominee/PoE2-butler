"""Public, unauthenticated read of a shared item snapshot."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_session
from app.db.models import ItemShare
from app.domain.item import coerce_item_dict

router = APIRouter(prefix="/api/public", tags=["public"])


class PublicItemResponse(BaseModel):
    league: str
    item: dict


@router.get("/items/{share_id}", summary="Read a shared item (no auth)")
async def get_public_item(
    share_id: str,
    db: AsyncSession = Depends(get_session),
) -> PublicItemResponse:
    try:
        sid = uuid.UUID(share_id)
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid_share_id",
        ) from ve
    row = await db.get(ItemShare, sid)
    if row is None or row.revoked_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="share_not_found")
    item = coerce_item_dict(row.item_raw)
    return PublicItemResponse(league=row.league, item=item.model_dump())
