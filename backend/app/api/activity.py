"""Activity log: diff current vs previous stash/character snapshots.

Returns new items (added since last refresh) and changed items (mods or
stats differ).  Relies on ``Snapshot.prev_payload`` which is populated by
``upsert_snapshot`` each time a snapshot is refreshed.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_session
from app.db.models import Snapshot, SnapshotKind, User
from app.deps import get_current_user
from app.domain.item import Item, parse_item

router = APIRouter(prefix="/api/activity", tags=["activity"])


# ── response models ────────────────────────────────────────────────────────────


class ChangedItem(BaseModel):
    old: Item
    new: Item


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


# ── diff helpers ───────────────────────────────────────────────────────────────


def _items_by_id(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        raw["id"]: raw
        for raw in (payload.get("items") or [])
        if isinstance(raw, dict) and raw.get("id")
    }


_CHANGE_KEYS = ("explicitMods", "implicitMods", "craftedMods", "enchantMods", "runeMods")


def _item_changed(old: dict[str, Any], new: dict[str, Any]) -> bool:
    for k in _CHANGE_KEYS:
        if old.get(k) != new.get(k):
            return True
    old_props = [(p.get("name"), p.get("values")) for p in (old.get("properties") or [])]
    new_props = [(p.get("name"), p.get("values")) for p in (new.get("properties") or [])]
    return old_props != new_props


def _diff_tab(
    old_p: dict[str, Any],
    new_p: dict[str, Any],
) -> tuple[list[Item], list[ChangedItem], list[Item]]:
    old_map = _items_by_id(old_p)
    new_map = _items_by_id(new_p)

    new_items = [parse_item(v) for k, v in new_map.items() if k not in old_map]
    removed = [parse_item(v) for k, v in old_map.items() if k not in new_map]
    changed = [
        ChangedItem(old=parse_item(old_map[k]), new=parse_item(v))
        for k, v in new_map.items()
        if k in old_map and _item_changed(old_map[k], v)
    ]
    return new_items, changed, removed


# ── endpoint ───────────────────────────────────────────────────────────────────


@router.get("", summary="Activity log: item changes since last refresh")
async def get_activity(
    league: str | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> ActivityResponse:
    effective_league = league or user.preferred_league or ""

    # Load all STASH_TAB snapshots for this user+league.
    stmt = (
        select(Snapshot)
        .where(Snapshot.user_id == user.id)
        .where(Snapshot.kind == SnapshotKind.STASH_TAB)
        .where(Snapshot.key.startswith(f"{effective_league}:"))
    )
    result = await db.execute(stmt)
    snaps: list[Snapshot] = list(result.scalars().all())

    entries: list[ActivityEntry] = []
    any_prev = False

    for snap in snaps:
        tab_id = snap.key.split(":", 1)[1] if ":" in snap.key else snap.key
        tab_name = _tab_name(snap.payload, tab_id)

        if snap.prev_payload is None:
            continue

        any_prev = True
        new_items, changed, removed = _diff_tab(snap.prev_payload, snap.payload)

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

    total_new = sum(len(e.new_items) for e in entries)
    total_changed = sum(len(e.changed_items) for e in entries)

    return ActivityResponse(
        league=effective_league,
        has_prev=any_prev,
        total_new=total_new,
        total_changed=total_changed,
        entries=entries,
    )


def _tab_name(payload: dict[str, Any], fallback: str) -> str:
    return str(payload.get("tab", {}).get("name") or fallback)
