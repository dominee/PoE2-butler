"""Characters endpoints: list and detail (equipped gear)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.ggg import GGGClient, GGGError, ggg_error_implies_reauth
from app.db.base import get_session
from app.db.models import SnapshotKind, User
from app.deps import get_cipher, get_current_user, get_ggg_client
from app.domain.character import (
    CharacterDetail,
    CharacterSummary,
    parse_detail,
    parse_summaries,
)
from app.domain.snapshot_diff import CharacterSnapshotChangeLine
from app.security.crypto import TokenCipher
from app.services.character_snapshot_history import (
    get_character_snapshot_history,
    list_character_snapshots,
)
from app.services.snapshot import ensure_character_detail, get_latest_snapshot

router = APIRouter(prefix="/api/characters", tags=["characters"])


class CharactersResponse(BaseModel):
    league: str | None
    characters: list[CharacterSummary]


class CharacterSnapshotChange(BaseModel):
    kind: Literal["new", "changed", "removed"]
    label: str


class CharacterSnapshotMeta(BaseModel):
    id: int | None
    fetched_at: datetime
    is_current: bool
    changes: list[CharacterSnapshotChange]


class CharacterSnapshotsResponse(BaseModel):
    character_name: str
    snapshots: list[CharacterSnapshotMeta]


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


@router.get("/{name}/snapshots", summary="Timeline metadata for character gear snapshots")
async def list_character_snapshot_timeline(
    name: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> CharacterSnapshotsResponse:
    meta = await list_character_snapshots(db, user_id=user.id, character_name=name)
    return CharacterSnapshotsResponse(
        character_name=name,
        snapshots=[
            CharacterSnapshotMeta(
                id=m.id,
                fetched_at=m.fetched_at,
                is_current=m.is_current,
                changes=[
                    CharacterSnapshotChange(kind=c.kind, label=c.label) for c in m.changes
                ],
            )
            for m in meta
        ],
    )


@router.get(
    "/{name}/snapshots/{history_id}",
    summary="Historic character detail from an archived snapshot",
)
async def get_historic_character(
    name: str,
    history_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> CharacterDetail:
    row = await get_character_snapshot_history(
        db, user_id=user.id, character_name=name, history_id=history_id
    )
    if row is None:
        raise HTTPException(status_code=404, detail="snapshot_not_found")
    detail = parse_detail(row.payload)
    return detail.model_copy(
        update={
            "snapshot_fetched_at": row.fetched_at,
            "is_historical": True,
        }
    )


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
        if ggg_error_implies_reauth(exc):
            raise HTTPException(status_code=401, detail="ggg_reauth_required") from exc
        raise HTTPException(status_code=502, detail="ggg_upstream_error") from exc
    await db.commit()
    return parse_detail(payload)
