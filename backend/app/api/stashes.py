"""Stash tabs endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.ggg import GGGClient
from app.db.base import get_session
from app.db.models import SnapshotKind, User
from app.deps import get_cipher, get_current_user, get_ggg_client, require_csrf
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
