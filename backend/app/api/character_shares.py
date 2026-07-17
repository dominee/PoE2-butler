"""Create and revoke world-readable character share links."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.ggg import GGGClient
from app.db.base import get_session
from app.db.models import CharacterShare, CharacterShareViewMode, User
from app.deps import get_cipher, get_current_user_mutate, get_ggg_client, get_redis
from app.services.character_share import resolve_character_detail_for_share
from app.services.share_ratelimit import enforce_character_share_create_limit

router = APIRouter(prefix="/api/character-shares", tags=["character-shares"])


class CreateCharacterShareRequest(BaseModel):
    league: str = Field(min_length=1, max_length=200)
    character_name: str = Field(min_length=1, max_length=200)
    history_id: int | None = None
    view_mode: Literal["simple", "detailed"] = "simple"


class CreateCharacterShareResponse(BaseModel):
    share_id: str
    public_path: str


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Create a public character share link",
    tags=["bot-api"],
)
async def create_character_share(
    body: CreateCharacterShareRequest,
    user: User = Depends(get_current_user_mutate),
    db: AsyncSession = Depends(get_session),
    redis: Any = Depends(get_redis),
    ggg: GGGClient = Depends(get_ggg_client),
    cipher: Any = Depends(get_cipher),
) -> CreateCharacterShareResponse:
    detail = await resolve_character_detail_for_share(
        session=db,
        user=user,
        character_name=body.character_name,
        history_id=body.history_id,
        ggg=ggg,
        cipher=cipher,
    )
    await enforce_character_share_create_limit(redis, user.id)
    share = CharacterShare(
        id=uuid.uuid4(),
        user_id=user.id,
        league=body.league,
        character_name=body.character_name,
        character_raw=detail.model_dump(mode="json"),
        view_mode=CharacterShareViewMode(body.view_mode),
    )
    db.add(share)
    await db.commit()
    return CreateCharacterShareResponse(
        share_id=str(share.id),
        public_path=f"/api/public/characters/{share.id}",
    )


@router.delete(
    "/{share_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke a character share link",
)
async def delete_character_share(
    share_id: str,
    user: User = Depends(get_current_user_mutate),
    db: AsyncSession = Depends(get_session),
) -> Response:
    try:
        sid = uuid.UUID(share_id)
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid_share_id",
        ) from ve
    row = await db.get(CharacterShare, sid)
    if row is None or row.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="share_not_found")
    if row.revoked_at is None:
        row.revoked_at = datetime.now(UTC)
        await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
