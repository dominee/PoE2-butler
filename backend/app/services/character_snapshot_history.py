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
from app.domain.snapshot_diff import (
    CharacterSnapshotChangeLine,
    character_gear_changed,
    summarize_character_changes,
)


@dataclass(frozen=True)
class CharacterSnapshotMeta:
    id: int | None
    fetched_at: datetime
    changes: list[CharacterSnapshotChangeLine]
    is_current: bool


async def archive_character_snapshot_if_changed(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    character_name: str,
    old_payload: dict,
    new_payload: dict,
    fetched_at: datetime,
) -> bool:
    """Persist gear state after a detected change; return True when archived."""
    if not character_gear_changed(old_payload, new_payload):
        return False
    changes = summarize_character_changes(old_payload, new_payload)
    session.add(
        CharacterSnapshotHistory(
            user_id=user_id,
            character_name=character_name,
            payload=copy.deepcopy(new_payload),
            fetched_at=fetched_at,
            changes=[c.model_dump() for c in changes],
        )
    )
    await session.flush()
    await _prune_character_history(session, user_id=user_id, character_name=character_name)
    return True


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


def _parse_changes(raw: list | None) -> list[CharacterSnapshotChangeLine]:
    if not raw:
        return []
    out: list[CharacterSnapshotChangeLine] = []
    for entry in raw:
        if isinstance(entry, dict):
            out.append(CharacterSnapshotChangeLine.model_validate(entry))
    return out


async def list_character_snapshots(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    character_name: str,
) -> list[CharacterSnapshotMeta]:
    """Return timeline oldest → newest; always includes live gear when cached."""
    hist_stmt = (
        select(CharacterSnapshotHistory)
        .where(CharacterSnapshotHistory.user_id == user_id)
        .where(CharacterSnapshotHistory.character_name == character_name)
        .order_by(CharacterSnapshotHistory.fetched_at.asc(), CharacterSnapshotHistory.id.asc())
    )
    hist_res = await session.execute(hist_stmt)
    history_rows = list(hist_res.scalars().all())

    current_stmt = (
        select(Snapshot)
        .where(Snapshot.user_id == user_id)
        .where(Snapshot.kind == SnapshotKind.CHARACTER)
        .where(Snapshot.key == character_name)
    )
    current_res = await session.execute(current_stmt)
    current = current_res.scalar_one_or_none()

    out: list[CharacterSnapshotMeta] = []
    for i, row in enumerate(history_rows):
        is_last = i == len(history_rows) - 1
        is_current = (
            is_last
            and current is not None
            and not character_gear_changed(row.payload, current.payload)
        )
        out.append(
            CharacterSnapshotMeta(
                id=row.id,
                fetched_at=row.fetched_at,
                changes=_parse_changes(row.changes),
                is_current=is_current,
            )
        )

    has_current_marker = bool(out) and out[-1].is_current
    if current is not None and not has_current_marker:
        out.append(
            CharacterSnapshotMeta(
                id=None,
                fetched_at=current.fetched_at,
                changes=[],
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
