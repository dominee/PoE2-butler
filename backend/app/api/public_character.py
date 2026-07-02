"""Public, unauthenticated read of a shared character snapshot."""

from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_session
from app.db.models import CharacterShare
from app.domain.character import CharacterDetail

router = APIRouter(prefix="/api/public", tags=["public"])


class PublicCharacterResponse(BaseModel):
    league: str
    character_name: str
    view_mode: Literal["simple", "detailed"]
    character: CharacterDetail


@router.get("/characters/{share_id}", summary="Read a shared character (no auth)")
async def get_public_character(
    share_id: str,
    db: AsyncSession = Depends(get_session),
) -> PublicCharacterResponse:
    try:
        sid = uuid.UUID(share_id)
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid_share_id",
        ) from ve
    row = await db.get(CharacterShare, sid)
    if row is None or row.revoked_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="share_not_found")
    character = CharacterDetail.model_validate(row.character_raw)
    return PublicCharacterResponse(
        league=row.league,
        character_name=row.character_name,
        view_mode=row.view_mode.value,
        character=character,
    )
