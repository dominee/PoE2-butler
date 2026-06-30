"""Character snapshot history archive and timeline listing."""

from __future__ import annotations

import copy
import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models import CharacterSnapshotHistory, Snapshot, SnapshotKind


@dataclass(frozen=True)
class CharacterSnapshotMeta:
    id: int | None
    fetched_at: datetime
    is_current: bool


async def archive_character_snapshot(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    character_name: str,
    payload: dict,
    fetched_at: datetime,
) -> None:
    """Persist a past CHARACTER payload and prune to the configured retention cap."""
    session.add(
        CharacterSnapshotHistory(
            user_id=user_id,
            character_name=character_name,
            payload=copy.deepcopy(payload),
            fetched_at=fetched_at,
        )
    )
    await session.flush()
    await _prune_character_history(session, user_id=user_id, character_name=character_name)


async def _prune_character_history(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    character_name: str,
) -> None:
    max_rows = get_settings().character_snapshot_history_max
    stmt = (
        select(CharacterSnapshotHistory.id)
        .where(CharacterSnapshotHistory.user_id == user_id)
        .where(CharacterSnapshotHistory.character_name == character_name)
        .order_by(CharacterSnapshotHistory.fetched_at.desc(), CharacterSnapshotHistory.id.desc())
    )
    res = await session.execute(stmt)
    ids = list(res.scalars().all())
    if len(ids) <= max_rows:
        return
    stale = ids[max_rows:]
    await session.execute(
        delete(CharacterSnapshotHistory).where(CharacterSnapshotHistory.id.in_(stale))
    )


async def list_character_snapshots(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    character_name: str,
) -> list[CharacterSnapshotMeta]:
    """Return timeline metadata oldest → newest, with the live snapshot last when present."""
    hist_stmt = (
        select(CharacterSnapshotHistory)
        .where(CharacterSnapshotHistory.user_id == user_id)
        .where(CharacterSnapshotHistory.character_name == character_name)
        .order_by(CharacterSnapshotHistory.fetched_at.asc(), CharacterSnapshotHistory.id.asc())
    )
    hist_res = await session.execute(hist_stmt)
    history_rows = list(hist_res.scalars().all())

    out: list[CharacterSnapshotMeta] = [
        CharacterSnapshotMeta(id=row.id, fetched_at=row.fetched_at, is_current=False)
        for row in history_rows
    ]

    current_stmt = (
        select(Snapshot)
        .where(Snapshot.user_id == user_id)
        .where(Snapshot.kind == SnapshotKind.CHARACTER)
        .where(Snapshot.key == character_name)
    )
    current_res = await session.execute(current_stmt)
    current = current_res.scalar_one_or_none()
    if current is not None:
        out.append(
            CharacterSnapshotMeta(
                id=None,
                fetched_at=current.fetched_at,
                is_current=True,
            )
        )
    return out


async def get_character_snapshot_history(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    character_name: str,
    history_id: int,
) -> CharacterSnapshotHistory | None:
    row = await session.get(CharacterSnapshotHistory, history_id)
    if row is None:
        return None
    if row.user_id != user_id or row.character_name != character_name:
        return None
    return row
