"""Activity log: diff current vs previous stash/character snapshots.

Returns new items (added since last refresh) and changed items (mods or
stats differ).  Uses ``Snapshot.prev_payload``: on each update
``upsert_snapshot`` shifts ``payload → prev_payload``; the **first** insert
for a key also stores a baseline copy in ``prev_payload`` so the UI can show
``has_prev`` without requiring two refresh cycles.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_session
from app.db.models import Snapshot, SnapshotKind, User
from app.deps import get_current_user_any
from app.domain.item import Item
from app.domain.snapshot_diff import ChangedItem, diff_payloads

router = APIRouter(prefix="/api/activity", tags=["activity"])


# ── response models ────────────────────────────────────────────────────────────


class ActivityEntry(BaseModel):
    tab_id: str
    tab_name: str
    new_items: list[Item]
    changed_items: list[ChangedItem]
    removed_items: list[Item]


class ActivityResponse(BaseModel):
    league: str
    has_prev: bool  # False when no previous snapshot exists yet
    total_new: int
    total_changed: int
    entries: list[ActivityEntry]
    # Character gear diffs (one entry per character with equipped item changes).
    gear_entries: list[ActivityEntry] = []


# ── endpoint ───────────────────────────────────────────────────────────────────


@router.get("", summary="Activity log: item changes since last refresh")
async def get_activity(
    league: str | None = None,
    user: User = Depends(get_current_user_any),
    db: AsyncSession = Depends(get_session),
) -> ActivityResponse:
    effective_league = league or user.preferred_league or ""

    # ── stash tab diffs ────────────────────────────────────────────────────────
    stmt = (
        select(Snapshot)
        .where(Snapshot.user_id == user.id)
        .where(Snapshot.kind == SnapshotKind.STASH_TAB)
        .where(Snapshot.key.startswith(f"{effective_league}:"))
    )
    result = await db.execute(stmt)
    stash_snaps: list[Snapshot] = list(result.scalars().all())

    entries: list[ActivityEntry] = []
    any_prev = False

    for snap in stash_snaps:
        tab_id = snap.key.split(":", 1)[1] if ":" in snap.key else snap.key
        tab_name = _tab_name(snap.payload, tab_id)

        if snap.prev_payload is None:
            continue

        any_prev = True
        new_items, changed, removed = diff_payloads(snap.prev_payload, snap.payload)

        if new_items or changed or removed:
            entries.append(
                ActivityEntry(
                    tab_id=tab_id,
                    tab_name=tab_name,
                    new_items=new_items,
                    changed_items=changed,
                    removed_items=removed,
                )
            )

    # ── character gear diffs ───────────────────────────────────────────────────
    char_stmt = (
        select(Snapshot)
        .where(Snapshot.user_id == user.id)
        .where(Snapshot.kind == SnapshotKind.CHARACTER)
    )
    char_result = await db.execute(char_stmt)
    char_snaps: list[Snapshot] = list(char_result.scalars().all())

    gear_entries: list[ActivityEntry] = []

    for snap in char_snaps:
        char_league = _character_league(snap.payload)
        if effective_league and char_league and char_league != effective_league:
            continue

        if snap.prev_payload is None:
            continue

        any_prev = True
        char_name = snap.key  # key is the character name
        new_items, changed, removed = diff_payloads(
            snap.prev_payload, snap.payload, character=True
        )

        if new_items or changed or removed:
            gear_entries.append(
                ActivityEntry(
                    tab_id=char_name,
                    tab_name=char_name,
                    new_items=new_items,
                    changed_items=changed,
                    removed_items=removed,
                )
            )

    total_new = sum(len(e.new_items) for e in entries) + sum(
        len(e.new_items) for e in gear_entries
    )
    total_changed = sum(len(e.changed_items) for e in entries) + sum(
        len(e.changed_items) for e in gear_entries
    )

    return ActivityResponse(
        league=effective_league,
        has_prev=any_prev,
        total_new=total_new,
        total_changed=total_changed,
        entries=entries,
        gear_entries=gear_entries,
    )


def _tab_name(payload: dict[str, Any], tab_id: str) -> str:
    tab = payload.get("tab") or {}
    return str(tab.get("name") or tab_id)


def _character_league(payload: dict[str, Any]) -> str:
    char = payload.get("character") or {}
    league = char.get("league")
    return str(league) if league else ""
