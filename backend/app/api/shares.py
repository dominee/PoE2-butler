"""Create and revoke world-readable item share links."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_session
from app.db.models import ItemShare, User
from app.deps import get_current_user, get_redis, require_csrf
from app.domain.item import coerce_item_dict
from app.services.share_ratelimit import enforce_share_create_limit

router = APIRouter(prefix="/api/shares", tags=["shares"])


class CreateShareRequest(BaseModel):
    league: str = Field(min_length=1, max_length=200)
    item: dict[str, Any]


class CreateShareResponse(BaseModel):
    share_id: str
    public_path: str


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Create a public item share link",
    dependencies=[Depends(require_csrf)],
)
async def create_share(
    body: CreateShareRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
    redis: Any = Depends(get_redis),
) -> CreateShareResponse:
    item = coerce_item_dict(body.item)
    await enforce_share_create_limit(redis, user.id)
    share = ItemShare(
        id=uuid.uuid4(),
        user_id=user.id,
        league=body.league,
        item_raw=item.model_dump(mode="json"),
    )
    db.add(share)
    await db.commit()
    return CreateShareResponse(
        share_id=str(share.id),
        public_path=f"/api/public/items/{share.id}",
    )


@router.delete(
    "/{share_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke a share link",
    dependencies=[Depends(require_csrf)],
)
async def delete_share(
    share_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> Response:
    try:
        sid = uuid.UUID(share_id)
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid_share_id",
        ) from ve
    row = await db.get(ItemShare, sid)
    if row is None or row.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="share_not_found")
    row.revoked_at = datetime.now(UTC)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
