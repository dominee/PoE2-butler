"""Tests for user activity event logging."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import func, select

from app.db.models import User, UserActivityEvent, UserActivityEventType
from app.services.snapshot import SnapshotOutcome, refresh_user_snapshot
from app.services.user_activity import record_user_activity


@pytest.mark.asyncio
async def test_record_user_activity_inserts_row(app_stack) -> None:
    _app, client, mock_app = app_stack
    from tests.test_auth_flow import _full_login

    await _full_login(client, mock_app)

    from app.db import base as db_base

    async with db_base._session_factory()() as db:
        login_count = await db.scalar(
            select(func.count())
            .select_from(UserActivityEvent)
            .where(UserActivityEvent.event_type == UserActivityEventType.LOGIN)
        )
        refresh_count = await db.scalar(
            select(func.count())
            .select_from(UserActivityEvent)
            .where(UserActivityEvent.event_type == UserActivityEventType.REFRESH)
        )
    assert (login_count or 0) >= 1
    assert (refresh_count or 0) >= 1


@pytest.mark.asyncio
async def test_refresh_user_snapshot_records_refresh_event(app_stack, monkeypatch) -> None:
    _app, _client, _mock_app = app_stack
    from app.db import base as db_base

    user_id = uuid.uuid4()
    async with db_base._session_factory()() as db:
        db.add(
            User(
                id=user_id,
                ggg_account_name=f"test_{user_id.hex[:8]}",
                realm="pc",
            )
        )
        await db.commit()

    class FakeGGG:
        async def get_profile(self, _access: str) -> dict:
            return {"name": "x"}

        async def get_leagues(self, _access: str) -> dict:
            return {"leagues": []}

        async def get_characters(self, _access: str, *, revalidate: bool = False) -> dict:
            return {"characters": []}

    async def fake_get_valid_ggg_access(*_args, **_kwargs) -> str:
        return "token"

    monkeypatch.setattr(
        "app.services.snapshot.get_valid_ggg_access",
        fake_get_valid_ggg_access,
    )

    async with db_base._session_factory()() as db:
        user = await db.get(User, user_id)
        assert user is not None
        outcome = await refresh_user_snapshot(
            session=db,
            user=user,
            ggg=FakeGGG(),  # type: ignore[arg-type]
            cipher=None,  # type: ignore[arg-type]
        )
        await db.commit()
        assert isinstance(outcome, SnapshotOutcome)

        refresh_count = await db.scalar(
            select(func.count())
            .select_from(UserActivityEvent)
            .where(
                UserActivityEvent.user_id == user_id,
                UserActivityEvent.event_type == UserActivityEventType.REFRESH,
            )
        )
    assert (refresh_count or 0) == 1


@pytest.mark.asyncio
async def test_record_user_activity_direct(app_stack) -> None:
    from app.db import base as db_base

    user_id = uuid.uuid4()
    async with db_base._session_factory()() as db:
        db.add(
            User(
                id=user_id,
                ggg_account_name=f"direct_{user_id.hex[:8]}",
                realm="pc",
            )
        )
        await record_user_activity(db, user_id=user_id, event_type=UserActivityEventType.LOGIN)
        await db.commit()

        row = (
            await db.execute(
                select(UserActivityEvent).where(UserActivityEvent.user_id == user_id)
            )
        ).scalar_one()
        assert row.event_type == UserActivityEventType.LOGIN
