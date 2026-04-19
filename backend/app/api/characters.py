"""Characters endpoints: list and detail (equipped gear)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.ggg import GGGClient, GGGError
from app.db.base import get_session
from app.db.models import SnapshotKind, User
from app.deps import get_cipher, get_current_user, get_ggg_client
from app.domain.character import (
    CharacterDetail,
    CharacterSummary,
    parse_detail,
    parse_summaries,
)
from app.security.crypto import TokenCipher
from app.services.snapshot import ensure_character_detail, get_latest_snapshot

router = APIRouter(prefix="/api/characters", tags=["characters"])


class CharactersResponse(BaseModel):
    league: str | None
    characters: list[CharacterSummary]


@router.get("", summary="List characters for a league")
async def list_characters(
    league: str | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> CharactersResponse:
    snap = await get_latest_snapshot(db, user.id, SnapshotKind.CHARACTERS)
    if snap is None:
        return CharactersResponse(league=league, characters=[])
    summaries = parse_summaries(snap.payload)
    if league:
        summaries = [c for c in summaries if c.league == league]
    return CharactersResponse(league=league, characters=summaries)


@router.get("/{name}", summary="Character detail with equipped items")
async def get_character(
    name: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
    ggg: GGGClient = Depends(get_ggg_client),
    cipher: TokenCipher = Depends(get_cipher),
) -> CharacterDetail:
    try:
        payload = await ensure_character_detail(
            session=db, user=user, ggg=ggg, cipher=cipher, name=name
        )
    except GGGError as exc:
        if exc.status_code == 404:
            raise HTTPException(status_code=404, detail="character_not_found") from exc
        raise HTTPException(status_code=502, detail="ggg_upstream_error") from exc
    await db.commit()
    return parse_detail(payload)
