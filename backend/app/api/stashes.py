"""Stash tabs endpoints."""

from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.ggg import GGGClient
from app.db.base import get_session
from app.db.models import Snapshot, SnapshotKind, User
from app.deps import get_cipher, get_current_user, get_ggg_client, require_csrf
from app.domain.item import parse_item
from app.domain.stash import StashTab, StashTabSummary, parse_tab, parse_tab_list
from app.security.crypto import TokenCipher
from app.services.snapshot import get_latest_snapshot, refresh_stashes

router = APIRouter(prefix="/api/stashes", tags=["stashes"])


class StashListResponse(BaseModel):
    league: str
    tabs: list[StashTabSummary]


@router.get("", summary="List stash tabs for a league")
async def list_stashes(
    league: str = Query(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> StashListResponse:
    snap = await get_latest_snapshot(db, user.id, SnapshotKind.STASH_LIST, key=league)
    tabs: list[StashTabSummary] = []
    if snap is not None:
        tabs = parse_tab_list(snap.payload)
    return StashListResponse(league=league, tabs=tabs)


# ── Cross-tab search ─────────────────────────────────────────────────────────
# NOTE: must be declared BEFORE the /{tab_id} route so FastAPI doesn't
# match the literal string "search" as a tab_id path parameter.

class SearchResult(BaseModel):
    tab_id: str
    tab_name: str
    tab_index: int
    items: list  # list[Item] serialised — reuse Item model


class StashSearchResponse(BaseModel):
    league: str
    query: str
    results: list[SearchResult]
    total_items: int


@router.get("/search", summary="Search items across all stash tabs in a league")
async def search_stash(
    league: str = Query(...),
    q: str = Query(..., min_length=2),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> StashSearchResponse:
    """Case-insensitive substring search across all cached stash-tab snapshots."""
    q_stripped = q.strip()
    if len(q_stripped) < 2:
        return StashSearchResponse(league=league, query=q, results=[], total_items=0)

    # Tab list metadata (name, index) for labelling results.
    list_snap = await get_latest_snapshot(db, user.id, SnapshotKind.STASH_LIST, key=league)
    tab_meta: dict[str, StashTabSummary] = {}
    if list_snap:
        for summary in parse_tab_list(list_snap.payload):
            tab_meta[summary.id] = summary

    # All STASH_TAB snapshots for this user & league.
    prefix = f"{league}:"
    stmt = select(Snapshot).where(
        Snapshot.user_id == user.id,
        Snapshot.kind == SnapshotKind.STASH_TAB,
        Snapshot.key.like(f"{prefix}%"),
    )
    rows = (await db.execute(stmt)).scalars().all()

    pattern = re.compile(re.escape(q_stripped), re.IGNORECASE)
    search_results: list[SearchResult] = []
    total = 0

    for snap in rows:
        tab_id = snap.key.removeprefix(prefix)
        meta = tab_meta.get(tab_id) or StashTabSummary(id=tab_id, name=tab_id, index=0)

        raw_items = (snap.payload or {}).get("items") or []
        matched = []
        for raw in raw_items:
            if not isinstance(raw, dict):
                continue
            haystack = " ".join(
                filter(
                    None,
                    [
                        raw.get("name", ""),
                        raw.get("typeLine", ""),
                        raw.get("baseType", ""),
                        *(raw.get("explicitMods") or []),
                        *(raw.get("implicitMods") or []),
                        *(raw.get("craftedMods") or []),
                    ],
                )
            )
            if pattern.search(haystack):
                matched.append(parse_item(raw))

        if matched:
            search_results.append(
                SearchResult(
                    tab_id=tab_id,
                    tab_name=meta.name,
                    tab_index=meta.index,
                    items=[item.model_dump() for item in matched],
                )
            )
            total += len(matched)

    search_results.sort(key=lambda r: r.tab_index)
    return StashSearchResponse(league=league, query=q, results=search_results, total_items=total)


# ── Tab contents ─────────────────────────────────────────────────────────────

@router.get("/{tab_id}", summary="Stash tab contents")
async def get_stash_tab(
    tab_id: str,
    league: str = Query(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> StashTab:
    list_snap = await get_latest_snapshot(db, user.id, SnapshotKind.STASH_LIST, key=league)
    if list_snap is None:
        raise HTTPException(status_code=404, detail="no_stash_list")
    tabs = parse_tab_list(list_snap.payload)
    summary = next((t for t in tabs if t.id == tab_id), None)
    if summary is None:
        raise HTTPException(status_code=404, detail="tab_not_found")

    tab_snap = await get_latest_snapshot(
        db, user.id, SnapshotKind.STASH_TAB, key=f"{league}:{tab_id}"
    )
    if tab_snap is None:
        raise HTTPException(status_code=404, detail="tab_not_cached")
    return parse_tab(summary, tab_snap.payload)


# ── Stash refresh ────────────────────────────────────────────────────────────

class RefreshStashesRequest(BaseModel):
    league: str


@router.post(
    "/refresh",
    summary="Refresh stash snapshot for a league",
    dependencies=[Depends(require_csrf)],
)
async def refresh_stash_tabs(
    body: RefreshStashesRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
    ggg: GGGClient = Depends(get_ggg_client),
    cipher: TokenCipher = Depends(get_cipher),
) -> dict[str, str]:
    await refresh_stashes(session=db, user=user, ggg=ggg, cipher=cipher, league=body.league)
    await db.commit()
    return {"status": "ok"}
