"""Resolve character detail payloads for share creation."""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.ggg import GGGClient
from app.db.models import SnapshotKind, User
from app.domain.character import CharacterDetail, parse_detail
from app.security.crypto import TokenCipher
from app.services.character_snapshot_history import get_character_snapshot_history
from app.services.snapshot import ensure_character_detail, get_latest_snapshot


async def resolve_character_detail_for_share(
    *,
    session: AsyncSession,
    user: User,
    character_name: str,
    history_id: int | None,
    ggg: GGGClient,
    cipher: TokenCipher,
) -> CharacterDetail:
    if history_id is not None:
        row = await get_character_snapshot_history(
            session,
            user_id=user.id,
            character_name=character_name,
            history_id=history_id,
        )
        if row is None:
            raise HTTPException(status_code=404, detail="snapshot_not_found")
        return parse_detail(row.payload).model_copy(
            update={
                "snapshot_fetched_at": row.fetched_at,
                "is_historical": True,
            }
        )

    snap = await get_latest_snapshot(
        session, user.id, SnapshotKind.CHARACTER, key=character_name
    )
    if snap is not None:
        detail = parse_detail(snap.payload)
        return detail.model_copy(
            update={
                "snapshot_fetched_at": snap.fetched_at,
                "is_historical": False,
            }
        )

    payload = await ensure_character_detail(
        session=session,
        user=user,
        ggg=ggg,
        cipher=cipher,
        name=character_name,
    )
    return parse_detail(payload)
