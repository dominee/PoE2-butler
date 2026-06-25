"""GET /api/leagues: synthesize league list from CHARACTERS when LEAGUES snapshot absent."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import delete, update

from app.db import base as db_base
from app.db.models import Snapshot, SnapshotKind, User
from app.domain.character import parse_summaries
from app.domain.league import pick_league_from_characters
from tests.test_auth_flow import _full_login

RUNES_OF_ALDUR = "Runes of Aldur"
STANDARD = "Standard"


def _characters_payload(*entries: tuple[str, str]) -> dict:
    """Build a GGG-shaped /account/characters payload."""
    return {
        "characters": [
            {
                "id": name.lower(),
                "name": name,
                "class": "Warrior",
                "level": 90,
                "league": league,
            }
            for name, league in entries
        ]
    }


@pytest.mark.asyncio
async def test_leagues_falls_back_to_characters_snapshot(app_stack) -> None:  # type: ignore[no-untyped-def]
    """When LEAGUES snapshot is missing, unique character leagues populate the dropdown."""
    _app, client, mock_app = app_stack
    await _full_login(client, mock_app)
    me = (await client.get("/api/me")).json()
    user_id = uuid.UUID(me["id"])
    fac = db_base._session_factory()

    chars_payload = _characters_payload(
        ("BringTheRainz", RUNES_OF_ALDUR),
        ("StandardGuy", STANDARD),
    )

    async with fac() as session:
        await session.execute(
            delete(Snapshot).where(
                Snapshot.user_id == user_id,
                Snapshot.kind == SnapshotKind.LEAGUES,
            )
        )
        await session.execute(
            delete(Snapshot).where(
                Snapshot.user_id == user_id,
                Snapshot.kind == SnapshotKind.CHARACTERS,
            )
        )
        session.add(
            Snapshot(
                user_id=user_id,
                kind=SnapshotKind.CHARACTERS,
                key="",
                payload=chars_payload,
            )
        )
        await session.execute(
            update(User)
            .where(User.id == user_id)
            .values(preferred_league=RUNES_OF_ALDUR)
        )
        await session.commit()

    r = await client.get("/api/leagues")
    assert r.status_code == 200, r.text
    body = r.json()
    league_ids = {lg["id"] for lg in body["leagues"]}
    assert RUNES_OF_ALDUR in league_ids
    assert STANDARD in league_ids
    assert body["preferred"] == RUNES_OF_ALDUR
    assert body["current"] == RUNES_OF_ALDUR
    runes = next(lg for lg in body["leagues"] if lg["id"] == RUNES_OF_ALDUR)
    assert runes["current"] is True
    standard = next(lg for lg in body["leagues"] if lg["id"] == STANDARD)
    assert standard["current"] is False


@pytest.mark.asyncio
async def test_leagues_uses_ggg_snapshot_when_present(app_stack) -> None:  # type: ignore[no-untyped-def]
    """When LEAGUES snapshot exists, character snapshot is not used for the list."""
    _app, client, mock_app = app_stack
    await _full_login(client, mock_app)
    me = (await client.get("/api/me")).json()
    user_id = uuid.UUID(me["id"])
    fac = db_base._session_factory()

    ggg_leagues = {
        "leagues": [
            {"id": "Only From GGG", "realm": "pc", "current": True},
        ]
    }
    chars_payload = _characters_payload(("OtherChar", RUNES_OF_ALDUR))

    async with fac() as session:
        await session.execute(
            delete(Snapshot).where(
                Snapshot.user_id == user_id,
                Snapshot.kind == SnapshotKind.LEAGUES,
            )
        )
        session.add(
            Snapshot(
                user_id=user_id,
                kind=SnapshotKind.LEAGUES,
                key="",
                payload=ggg_leagues,
            )
        )
        await session.execute(
            delete(Snapshot).where(
                Snapshot.user_id == user_id,
                Snapshot.kind == SnapshotKind.CHARACTERS,
            )
        )
        session.add(
            Snapshot(
                user_id=user_id,
                kind=SnapshotKind.CHARACTERS,
                key="",
                payload=chars_payload,
            )
        )
        await session.commit()

    r = await client.get("/api/leagues")
    assert r.status_code == 200, r.text
    body = r.json()
    assert [lg["id"] for lg in body["leagues"]] == ["Only From GGG"]


@pytest.mark.asyncio
async def test_leagues_current_falls_back_to_preferred(app_stack) -> None:  # type: ignore[no-untyped-def]
    """When synthesized leagues have no current flag, current uses preferred_league."""
    _app, client, mock_app = app_stack
    await _full_login(client, mock_app)
    me = (await client.get("/api/me")).json()
    user_id = uuid.UUID(me["id"])
    fac = db_base._session_factory()

    chars_payload = _characters_payload(
        ("A", RUNES_OF_ALDUR),
        ("B", STANDARD),
    )

    async with fac() as session:
        await session.execute(
            delete(Snapshot).where(
                Snapshot.user_id == user_id,
                Snapshot.kind.in_([SnapshotKind.LEAGUES, SnapshotKind.CHARACTERS]),
            )
        )
        session.add(
            Snapshot(
                user_id=user_id,
                kind=SnapshotKind.CHARACTERS,
                key="",
                payload=chars_payload,
            )
        )
        # preferred_league not matching any character league → no current=True on leagues
        await session.execute(
            update(User)
            .where(User.id == user_id)
            .values(preferred_league="Legacy League")
        )
        await session.commit()

    r = await client.get("/api/leagues")
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["leagues"]) == 2
    assert body["current"] == "Legacy League"
    assert all(not lg["current"] for lg in body["leagues"])


def test_pick_league_from_characters_prefers_challenge_league() -> None:
    payload = _characters_payload(
        ("A", STANDARD),
        ("B", RUNES_OF_ALDUR),
        ("C", RUNES_OF_ALDUR),
    )
    summaries = parse_summaries(payload)
    assert pick_league_from_characters(summaries) == RUNES_OF_ALDUR


@pytest.mark.asyncio
async def test_leagues_default_league_when_no_snapshots(app_stack, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """When no league/character snapshots exist, GGG_DEFAULT_LEAGUE fills the dropdown."""
    from pydantic import SecretStr

    from app import config as app_config
    from app import deps as app_deps
    from app.api import leagues as leagues_api
    from app.config import Settings

    _app, client, mock_app = app_stack
    await _full_login(client, mock_app)
    me = (await client.get("/api/me")).json()
    user_id = uuid.UUID(me["id"])
    fac = db_base._session_factory()

    base = app_config.get_settings()
    patched = Settings(
        environment=base.environment,
        app_secret_key=base.app_secret_key,
        session_signing_key=base.session_signing_key,
        ggg_oauth_base_url=base.ggg_oauth_base_url,
        ggg_api_base_url=base.ggg_api_base_url,
        ggg_client_id=base.ggg_client_id,
        ggg_client_secret=SecretStr(base.ggg_client_secret.get_secret_value()),
        ggg_redirect_uri=base.ggg_redirect_uri,
        ggg_scopes=base.ggg_scopes,
        ggg_default_league=RUNES_OF_ALDUR,
    )
    monkeypatch.setattr(app_config, "get_settings", lambda: patched)
    monkeypatch.setattr(app_deps, "get_settings", lambda: patched)
    monkeypatch.setattr(leagues_api, "get_settings", lambda: patched)

    async with fac() as session:
        await session.execute(
            delete(Snapshot).where(
                Snapshot.user_id == user_id,
                Snapshot.kind.in_([SnapshotKind.LEAGUES, SnapshotKind.CHARACTERS]),
            )
        )
        await session.execute(
            update(User).where(User.id == user_id).values(preferred_league=None)
        )
        await session.commit()

    r = await client.get("/api/leagues")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["leagues"] == [
        {"id": RUNES_OF_ALDUR, "realm": "pc", "description": None, "current": True}
    ]
    assert body["current"] == RUNES_OF_ALDUR
    assert body["preferred"] == RUNES_OF_ALDUR
