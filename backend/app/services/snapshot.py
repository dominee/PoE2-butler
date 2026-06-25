"""Snapshot service: fetch GGG data and persist it as JSONB payloads.

Read-mostly: the one place in the backend that writes data tables. Called from
the OAuth callback and from the ``arq`` worker.
"""

from __future__ import annotations

import copy
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.ggg import GGGClient, GGGError
from app.config import get_settings
from app.db.models import Snapshot, SnapshotKind, User
from app.domain.character import parse_summaries
from app.domain.league import parse_leagues, pick_current_league, pick_league_from_characters
from app.logging import get_logger
from app.security.crypto import TokenCipher
from app.services.ggg_token import force_refresh_ggg_access, get_valid_ggg_access

log = get_logger("app.services.snapshot")


@dataclass
class SnapshotOutcome:
    profile: bool = False
    leagues: bool = False
    characters: bool = False
    errors: list[str] | None = None


async def upsert_snapshot(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    kind: SnapshotKind,
    key: str,
    payload: dict,
) -> None:
    """Insert or update a snapshot identified by (user_id, kind, key).

    Kept dialect-agnostic: one SELECT followed by INSERT or field updates.
    Concurrent refreshes of the same user serialize through the per-user
    Redis cooldown, so the race window here is negligible.
    """
    existing = await get_latest_snapshot(session, user_id, kind, key)
    now = datetime.now(UTC)
    if existing is None:
        # Baseline copy so GET /api/activity can treat the tab as tracked immediately;
        # the first refresh then shifts payload → prev_payload and surfaces real diffs.
        session.add(
            Snapshot(
                user_id=user_id,
                kind=kind,
                key=key,
                payload=payload,
                prev_payload=copy.deepcopy(payload),
                fetched_at=now,
            )
        )
    else:
        # Preserve current payload as previous before overwriting — this is the
        # basis for the activity log diff on the next refresh.
        existing.prev_payload = existing.payload
        existing.payload = payload
        existing.fetched_at = now


async def get_latest_snapshot(
    session: AsyncSession, user_id: uuid.UUID, kind: SnapshotKind, key: str = ""
) -> Snapshot | None:
    stmt = (
        select(Snapshot)
        .where(Snapshot.user_id == user_id)
        .where(Snapshot.kind == kind)
        .where(Snapshot.key == key)
    )
    res = await session.execute(stmt)
    return res.scalar_one_or_none()


async def delete_character_snapshots(session: AsyncSession, user_id: uuid.UUID) -> None:
    """Remove cached per-character payloads so the next read refetches from GGG (or mock)."""
    await session.execute(
        delete(Snapshot).where(
            Snapshot.user_id == user_id,
            Snapshot.kind == SnapshotKind.CHARACTER,
        )
    )


async def refresh_character_gear_snapshots(
    *,
    session: AsyncSession,
    user: User,
    ggg: GGGClient,
    cipher: TokenCipher,
    league: str,
) -> None:
    """Re-fetch and persist CHARACTER rows for every account toon in ``league``.

    Manual :func:`delete_character_snapshots` clears lazy detail caches; without this
    follow-up fetch, equipped gear would be missing until each character is opened again.
    """
    league = league.strip()
    if not league:
        return
    snap = await get_latest_snapshot(session, user.id, SnapshotKind.CHARACTERS)
    if snap is None:
        return
    summaries = parse_summaries(snap.payload)
    in_league = [c for c in summaries if (c.league or "").strip() == league]
    for c in in_league:
        name = (c.name or "").strip()
        if not name:
            continue
        try:
            await ensure_character_detail(
                session=session, user=user, ggg=ggg, cipher=cipher, name=name
            )
        except Exception as exc:  # noqa: BLE001
            log.warning(
                "snapshot.character_gear_refresh_failed",
                user_id=str(user.id),
                character=name,
                error=str(exc),
            )


async def refresh_user_snapshot(
    *,
    session: AsyncSession,
    user: User,
    ggg: GGGClient,
    cipher: TokenCipher,
    include_stashes_for_league: str | None = None,
    revalidate_character_list: bool = False,
) -> SnapshotOutcome:
    """Fetch profile, leagues and characters for ``user`` and persist them.

    Character details are fetched lazily on demand. Stash tabs for a specific
    league can be fetched inline by passing ``include_stashes_for_league``;
    otherwise a separate :func:`refresh_stashes` call is used.
    """
    outcome = SnapshotOutcome(errors=[])

    try:
        access = await get_valid_ggg_access(session, user, ggg, cipher)
    except RuntimeError:
        outcome.errors.append("no_tokens")
        return outcome

    try:
        profile = await ggg.get_profile(access)
        await upsert_snapshot(
            session, user_id=user.id, kind=SnapshotKind.PROFILE, key="", payload=profile
        )
        outcome.profile = True
    except Exception as exc:  # noqa: BLE001
        log.error("snapshot.profile_failed", error=str(exc), exc_info=True)
        outcome.errors.append(f"profile:{exc}")

    leagues_payload: dict | None = None
    try:
        leagues_payload = await ggg.get_leagues(access)
        await upsert_snapshot(
            session, user_id=user.id, kind=SnapshotKind.LEAGUES, key="", payload=leagues_payload
        )
        outcome.leagues = True
        # Promote the current league to the user row on first login (preferred_league
        # is None) so the session carries a meaningful league from the very first request.
        if user.preferred_league is None:
            current = pick_current_league(parse_leagues(leagues_payload))
            if current:
                user.preferred_league = current
    except Exception as exc:  # noqa: BLE001
        # account:leagues scope may not be granted (e.g. GGG PoE2 grant is profile +
        # characters only). Log at info level — it is expected when the scope is absent.
        log.info(
            "snapshot.leagues_skipped",
            error=str(exc),
            note="preferred_league will be inferred from characters",
        )
        outcome.errors.append(f"leagues:{exc}")

    # Stash list + tab payloads are fast against the mock; Poe.ninja ``revalidate=1`` on the
    # character list can take many minutes. Run stashes first so manual refresh still fills
    # STASH_TAB rows even when get_characters times out.
    if include_stashes_for_league:
        try:
            await _refresh_stashes(
                session, user=user, ggg=ggg, access=access, league=include_stashes_for_league
            )
        except Exception as exc:  # noqa: BLE001
            outcome.errors.append(f"stashes:{exc}")

    try:
        chars = await ggg.get_characters(access, revalidate=revalidate_character_list)
        await upsert_snapshot(
            session, user_id=user.id, kind=SnapshotKind.CHARACTERS, key="", payload=chars
        )
        outcome.characters = True
        # Fallback: if account:leagues was unavailable, infer preferred_league from
        # the character list (each character carries its current league name).
        if user.preferred_league is None:
            inferred = pick_league_from_characters(parse_summaries(chars))
            if inferred:
                user.preferred_league = inferred
                log.info("snapshot.league_inferred_from_characters", league=inferred)
    except Exception as exc:  # noqa: BLE001
        log.error("snapshot.characters_failed", error=str(exc), exc_info=True)
        outcome.errors.append(f"characters:{exc}")

    user.last_refreshed_at = datetime.now(UTC)
    return outcome


async def _refresh_stashes(
    session: AsyncSession,
    *,
    user: User,
    ggg: GGGClient,
    access: str,
    league: str,
) -> None:
    """Fetch and persist the stash tab list + per-tab contents for a league.

    Respects GGG rate limits implicitly via the httpx client; one call per
    tab is acceptable for the public league and small tab counts we expect.
    """
    tab_list_payload = await ggg.get_stash_list(access, league)
    await upsert_snapshot(
        session,
        user_id=user.id,
        kind=SnapshotKind.STASH_LIST,
        key=league,
        payload=tab_list_payload,
    )

    from app.domain.stash import parse_tab_list

    tabs = parse_tab_list(tab_list_payload)
    for tab in tabs:
        try:
            tab_payload = await ggg.get_stash_tab(access, league, tab.id)
            await upsert_snapshot(
                session,
                user_id=user.id,
                kind=SnapshotKind.STASH_TAB,
                key=f"{league}:{tab.id}",
                payload=tab_payload,
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("snapshot.stash_tab_failed", league=league, tab_id=tab.id, error=str(exc))


async def refresh_stashes(
    *, session: AsyncSession, user: User, ggg: GGGClient, cipher: TokenCipher, league: str
) -> None:
    access = await get_valid_ggg_access(session, user, ggg, cipher)
    await _refresh_stashes(session, user=user, ggg=ggg, access=access, league=league)


def _character_detail_snapshot_ttl_seconds(payload: dict[str, Any]) -> float:
    """Use a short TTL for empty gear when the backend talks to the local mock.

    The mock seeds a minimal character (no items) then warms full Poe.ninja data in
    the background; without this, the 60s snapshot cache keeps the empty doll.
    """
    settings = get_settings()
    api = settings.ggg_api_base_url.lower()
    if "mock-ggg" not in api and "127.0.0.1" not in api:
        return 60.0
    items = payload.get("items")
    if items is None:
        return 5.0
    if isinstance(items, (list, tuple)) and len(items) == 0:
        return 5.0
    return 60.0


async def ensure_character_detail(
    *,
    session: AsyncSession,
    user: User,
    ggg: GGGClient,
    cipher: TokenCipher,
    name: str,
) -> dict:
    """Fetch character detail on demand and cache it in snapshots."""
    existing = await get_latest_snapshot(session, user.id, SnapshotKind.CHARACTER, key=name)
    if existing is not None:
        age = datetime.now(UTC) - existing.fetched_at
        ttl = _character_detail_snapshot_ttl_seconds(existing.payload)
        if age.total_seconds() < ttl:
            return existing.payload

    access = await get_valid_ggg_access(session, user, ggg, cipher)
    try:
        payload = await ggg.get_character(access, name)
    except GGGError as exc:
        if exc.status_code == 401:
            access = await force_refresh_ggg_access(session, user, ggg, cipher)
            payload = await ggg.get_character(access, name)
        else:
            raise
    await upsert_snapshot(
        session, user_id=user.id, kind=SnapshotKind.CHARACTER, key=name, payload=payload
    )
    return payload
