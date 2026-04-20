"""Snapshot service: fetch GGG data and persist it as JSONB payloads.

Read-mostly: the one place in the backend that writes data tables. Called from
the OAuth callback and from the ``arq`` worker.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.ggg import GGGClient
from app.db.models import Snapshot, SnapshotKind, User, UserToken
from app.domain.league import parse_leagues, pick_current_league
from app.logging import get_logger
from app.security.crypto import TokenCipher

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
        session.add(
            Snapshot(user_id=user_id, kind=kind, key=key, payload=payload, fetched_at=now)
        )
    else:
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


async def refresh_user_snapshot(
    *,
    session: AsyncSession,
    user: User,
    ggg: GGGClient,
    cipher: TokenCipher,
    include_stashes_for_league: str | None = None,
) -> SnapshotOutcome:
    """Fetch profile, leagues and characters for ``user`` and persist them.

    Character details are fetched lazily on demand. Stash tabs for a specific
    league can be fetched inline by passing ``include_stashes_for_league``;
    otherwise a separate :func:`refresh_stashes` call is used.
    """
    outcome = SnapshotOutcome(errors=[])

    tokens = await session.get(UserToken, user.id)
    if tokens is None:
        outcome.errors.append("no_tokens")
        return outcome

    access = cipher.decrypt_str(tokens.access_token_enc)

    try:
        profile = await ggg.get_profile(access)
        await upsert_snapshot(
            session, user_id=user.id, kind=SnapshotKind.PROFILE, key="", payload=profile
        )
        outcome.profile = True
    except Exception as exc:  # noqa: BLE001
        log.error("snapshot.profile_failed", error=str(exc), exc_info=True)
        outcome.errors.append(f"profile:{exc}")

    try:
        leagues = await ggg.get_leagues(access)
        await upsert_snapshot(
            session, user_id=user.id, kind=SnapshotKind.LEAGUES, key="", payload=leagues
        )
        outcome.leagues = True
        # Promote the current league to the user row on first login (preferred_league
        # is None) so the session carries a meaningful league from the very first request.
        if user.preferred_league is None:
            current = pick_current_league(parse_leagues(leagues))
            if current:
                user.preferred_league = current
    except Exception as exc:  # noqa: BLE001
        log.error("snapshot.leagues_failed", error=str(exc), exc_info=True)
        outcome.errors.append(f"leagues:{exc}")

    try:
        chars = await ggg.get_characters(access)
        await upsert_snapshot(
            session, user_id=user.id, kind=SnapshotKind.CHARACTERS, key="", payload=chars
        )
        outcome.characters = True
    except Exception as exc:  # noqa: BLE001
        log.error("snapshot.characters_failed", error=str(exc), exc_info=True)
        outcome.errors.append(f"characters:{exc}")

    if include_stashes_for_league:
        try:
            await _refresh_stashes(
                session, user=user, ggg=ggg, access=access, league=include_stashes_for_league
            )
        except Exception as exc:  # noqa: BLE001
            outcome.errors.append(f"stashes:{exc}")

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
    tokens = await session.get(UserToken, user.id)
    if tokens is None:
        raise RuntimeError("user_has_no_tokens")
    access = cipher.decrypt_str(tokens.access_token_enc)
    await _refresh_stashes(session, user=user, ggg=ggg, access=access, league=league)


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
        if age.total_seconds() < 60:
            return existing.payload

    tokens = await session.get(UserToken, user.id)
    if tokens is None:
        raise RuntimeError("user_has_no_tokens")
    access = cipher.decrypt_str(tokens.access_token_enc)
    payload = await ggg.get_character(access, name)
    await upsert_snapshot(
        session, user_id=user.id, kind=SnapshotKind.CHARACTER, key=name, payload=payload
    )
    return payload
