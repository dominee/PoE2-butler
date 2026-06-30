"""Operator backend routes (/api/admin/*)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from fakeredis.aioredis import FakeRedis
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app import deps as app_deps
from app.config import Settings
from app.db.base import Base
from app.db.models import ItemShare, User
from app.main import create_app
from app.security.sessions import SessionStore


@pytest.fixture
async def admin_client(monkeypatch):
    monkeypatch.setenv("ADMIN_INTERNAL_SECRET", "test-admin-secret")
    from app.config import get_settings

    get_settings.cache_clear()

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async def _get_session():
        async with factory() as session:
            yield session

    redis = FakeRedis(decode_responses=True)

    async def _fake_redis():
        yield redis

    app = create_app()

    async def _override_session():
        async with factory() as session:
            yield session

    from app.db.base import get_session

    app.dependency_overrides[get_session] = _override_session
    app.dependency_overrides[app_deps.get_redis] = _fake_redis
    app.dependency_overrides[app_deps.get_session_store] = lambda: SessionStore(redis, 3600)

    uid = uuid.uuid4()
    async with factory() as session:
        session.add(User(id=uid, ggg_account_name="ops#1", realm="pc"))
        await session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, uid, factory, redis

    get_settings.cache_clear()
    await engine.dispose()


@pytest.mark.asyncio
async def test_admin_ops_disabled_without_secret(monkeypatch) -> None:
    monkeypatch.delenv("ADMIN_INTERNAL_SECRET", raising=False)
    from app.config import get_settings

    get_settings.cache_clear()
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            f"/api/admin/users/{uuid.uuid4()}/logout",
            headers={"X-Admin-Internal-Secret": "nope"},
        )
        assert resp.status_code == 404
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_admin_logout_destroys_sessions(admin_client) -> None:
    client, uid, _factory, redis = admin_client
    store = SessionStore(redis, 3600)
    await store.create(str(uid))

    resp = await client.post(
        f"/api/admin/users/{uid}/logout",
        headers={"X-Admin-Internal-Secret": "test-admin-secret"},
    )
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


@pytest.mark.asyncio
async def test_admin_revoke_share(admin_client) -> None:
    client, uid, factory, _redis = admin_client
    share_id = uuid.uuid4()
    async with factory() as session:
        session.add(
            ItemShare(id=share_id, user_id=uid, league="L", item_raw={"id": "i1"})
        )
        await session.commit()

    resp = await client.post(
        f"/api/admin/shares/{share_id}/revoke",
        headers={"X-Admin-Internal-Secret": "test-admin-secret"},
    )
    assert resp.status_code == 200

    async with factory() as session:
        row = await session.get(ItemShare, share_id)
        assert row is not None
        assert row.revoked_at is not None
