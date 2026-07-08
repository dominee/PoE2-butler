"""Snapshot service: fetch GGG data and persist it as JSONB payloads.

Read-mostly: the one place in the backend that writes data tables. Called from
the OAuth callback and from the ``arq`` worker.
"""

from __future__ import annotations

import asyncio
import copy
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.ggg import GGGClient, GGGError
from app.config import get_settings
from app.db.models import Snapshot, SnapshotKind, User, UserActivityEventType
from app.domain.character import collect_character_items, parse_summaries
from app.domain.league import (
    _PERMANENT_LEAGUES,
    parse_leagues,
    pick_current_league,
    pick_league_from_characters,
)
from app.logging import get_logger
from app.security.crypto import TokenCipher
from app.services.character_snapshot_history import archive_character_snapshot_if_changed
from app.services.ggg_token import force_refresh_ggg_access, get_valid_ggg_access
from app.services.user_activity import record_user_activity

log = get_logger("app.services.snapshot")


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _as_utc(dt: datetime) -> datetime:
    """SQLite test DB may return naive timestamps for TIMESTAMPTZ columns."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


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
    previous_payload: dict | None = None,
    insert_prev_payload: dict | None = None,
) -> None:
    """Insert or update a snapshot identified by (user_id, kind, key).

    Kept dialect-agnostic: one SELECT followed by INSERT or field updates.
    Concurrent refreshes of the same user serialize through the per-user
    Redis cooldown, so the race window here is negligible.
    """
    existing = await get_latest_snapshot(session, user_id, kind, key)
    now = _utc_now()
    if kind == SnapshotKind.CHARACTER:
        old_payload = (
            previous_payload
            if previous_payload is not None
            else (existing.payload if existing is not None else None)
        )
        if old_payload is not None:
            await archive_character_snapshot_if_changed(
                session,
                user_id=user_id,
                character_name=key,
                old_payload=old_payload,
                new_payload=payload,
                fetched_at=now,
            )
    if existing is None:
        # Baseline for activity diff: after manual refresh re-insert, use the gear state
        # before refresh (insert_prev_payload) instead of duplicating the new payload.
        baseline = (
            copy.deepcopy(insert_prev_payload)
            if insert_prev_payload is not None
            else copy.deepcopy(payload)
        )
        session.add(
            Snapshot(
                user_id=user_id,
                kind=kind,
                key=key,
                payload=payload,
                prev_payload=baseline,
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


@dataclass
class CapturedCharacterSnapshot:
    """Payload captured before manual refresh clears CHARACTER rows."""

    payload: dict
    prev_payload: dict | None
    fetched_at: datetime | None = None


async def restore_character_snapshot(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    name: str,
    captured: CapturedCharacterSnapshot,
) -> None:
    """Re-insert cached gear after a failed refresh fetch (no archive side-effects)."""
    existing = await get_latest_snapshot(session, user_id, SnapshotKind.CHARACTER, key=name)
    if existing is not None:
        return
    when = captured.fetched_at
    if when is not None:
        when = _as_utc(when)
    session.add(
        Snapshot(
            user_id=user_id,
            kind=SnapshotKind.CHARACTER,
            key=name,
            payload=copy.deepcopy(captured.payload),
            prev_payload=(
                copy.deepcopy(captured.prev_payload)
                if captured.prev_payload is not None
                else copy.deepcopy(captured.payload)
            ),
            fetched_at=when or _utc_now(),
        )
    )


async def delete_character_snapshots(
    session: AsyncSession, user_id: uuid.UUID
) -> dict[str, CapturedCharacterSnapshot]:
    """Remove cached per-character payloads; return captured gear for re-insert."""
    stmt = select(Snapshot).where(
        Snapshot.user_id == user_id,
        Snapshot.kind == SnapshotKind.CHARACTER,
    )
    res = await session.execute(stmt)
    captured = {
        snap.key: CapturedCharacterSnapshot(
            payload=snap.payload,
            prev_payload=snap.prev_payload,
            fetched_at=snap.fetched_at,
        )
        for snap in res.scalars().all()
    }
    await session.execute(
        delete(Snapshot).where(
            Snapshot.user_id == user_id,
            Snapshot.kind == SnapshotKind.CHARACTER,
        )
    )
    return captured


async def refresh_character_gear_snapshots(
    *,
    session: AsyncSession,
    user: User,
    ggg: GGGClient,
    cipher: TokenCipher,
    league: str,
    captured_characters: dict[str, CapturedCharacterSnapshot] | None = None,
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
    spacing = max(float(get_settings().ggg_character_fetch_spacing_sec), 0.0)
    for idx, c in enumerate(in_league):
        if idx > 0 and spacing > 0:
            await asyncio.sleep(spacing)
        name = (c.name or "").strip()
        if not name:
            continue
        cap = (captured_characters or {}).get(name)
        try:
            await ensure_character_detail(
                session=session,
                user=user,
                ggg=ggg,
                cipher=cipher,
                name=name,
                previous_payload=cap.payload if cap is not None else None,
                insert_prev_payload=cap.payload if cap is not None else None,
            )
        except Exception as exc:  # noqa: BLE001
            log.warning(
                "snapshot.character_gear_refresh_failed",
                user_id=str(user.id),
                character=name,
                error=str(exc),
            )
            if cap is not None:
                await restore_character_snapshot(
                    session,
                    user_id=user.id,
                    name=name,
                    captured=cap,
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
        inferred = pick_league_from_characters(parse_summaries(chars))
        if inferred and inferred != user.preferred_league:
            current_is_permanent = (user.preferred_league or "").lower() in _PERMANENT_LEAGUES
            if user.preferred_league is None or current_is_permanent:
                user.preferred_league = inferred
                log.info("snapshot.league_inferred_from_characters", league=inferred)
        elif user.preferred_league is None:
            fallback = get_settings().ggg_default_league
            if fallback:
                user.preferred_league = fallback
                log.info("snapshot.league_default_fallback", league=fallback)
    except Exception as exc:  # noqa: BLE001
        log.error("snapshot.characters_failed", error=str(exc), exc_info=True)
        outcome.errors.append(f"characters:{exc}")

    user.last_refreshed_at = datetime.now(UTC)
    await record_user_activity(session, user_id=user.id, event_type=UserActivityEventType.REFRESH)
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
    if not collect_character_items(payload):
        return 5.0
    return 60.0


async def ensure_character_detail(
    *,
    session: AsyncSession,
    user: User,
    ggg: GGGClient,
    cipher: TokenCipher,
    name: str,
    previous_payload: dict | None = None,
    insert_prev_payload: dict | None = None,
) -> dict:
    """Fetch character detail on demand and cache it in snapshots."""
    existing = await get_latest_snapshot(session, user.id, SnapshotKind.CHARACTER, key=name)
    if existing is not None:
        age = _utc_now() - _as_utc(existing.fetched_at)
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
        elif exc.status_code == 429 and existing is not None:
            log.warning(
                "character_detail.ggg_429_serving_stale",
                character=name,
                user_id=str(user.id),
            )
            return existing.payload
        else:
            raise
    await upsert_snapshot(
        session,
        user_id=user.id,
        kind=SnapshotKind.CHARACTER,
        key=name,
        payload=payload,
        previous_payload=previous_payload,
        insert_prev_payload=insert_prev_payload,
    )
    return payload
