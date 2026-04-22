"""End-to-end style tests of the auth flow against the in-process mock-ggg.

We mount the real `mock-ggg` FastAPI app as the GGG upstream via an
``httpx.AsyncClient`` transport, mocking both OAuth2 and the resource endpoints.
Database and redis are both replaced with in-memory / fake backends so the
tests stay hermetic.
"""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

import httpx
import pytest
from fakeredis.aioredis import FakeRedis
from httpx import ASGITransport, AsyncClient

from app import deps as app_deps
from app.clients.ggg import GGGClient
from app.config import Settings
from app.db import base as db_base
from app.db.base import Base
from app.main import create_app


def _load_mock_ggg_app():
    # Add mock-ggg to sys.path so we can import its `app` package as `mock_ggg_app`.
    mock_dir = Path(__file__).resolve().parent.parent.parent / "mock-ggg"
    pkg_root = mock_dir
    spec = importlib.util.spec_from_file_location(
        "mock_ggg_app_main", pkg_root / "app" / "main.py"
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("failed to load mock-ggg")
    module = importlib.util.module_from_spec(spec)
    # The mock module uses relative path for fixtures; ensure its __file__ is right.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.app


@pytest.fixture
async def app_stack(monkeypatch, tmp_path):
    # In-memory SQLite for hermetic tests. The model types use
    # ``with_variant`` so JSON/UUID map cleanly on either dialect.
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    monkeypatch.setattr(db_base, "_session_factory", lambda: factory)
    monkeypatch.setattr(db_base, "get_engine", lambda: engine)

    # Fake redis for sessions + pending auth.
    redis = FakeRedis(decode_responses=True)
    app_deps._redis_singleton.cache_clear()
    monkeypatch.setattr(app_deps, "_redis_singleton", lambda: redis)

    # Load the mock-ggg app and wire a transport-routed httpx client to it.
    mock_app = _load_mock_ggg_app()
    mock_transport = ASGITransport(app=mock_app)

    # Settings pointing at the mock (URL is nominal; transport decides routing).
    from pydantic import SecretStr

    settings = Settings(
        environment="test",
        app_secret_key=SecretStr("AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="),
        session_signing_key=SecretStr("AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="),
        ggg_oauth_base_url="http://ggg-mock",
        ggg_api_base_url="http://ggg-mock",
        ggg_client_id="test-client",
        ggg_client_secret=SecretStr("test-secret"),
        ggg_redirect_uri="http://testserver/api/auth/callback",
        cors_allow_origins=["http://testserver"],
    )

    from app import config as app_config

    monkeypatch.setattr(app_config, "get_settings", lambda: settings)
    monkeypatch.setattr(app_deps, "get_settings", lambda: settings)
    from app import main as app_main

    monkeypatch.setattr(app_main, "get_settings", lambda: settings)
    app_deps._cipher_singleton.cache_clear()

    # GGG client dependency: build one whose transport points at the mock app.
    async def _ggg_client_override():
        client = GGGClient(
            settings,
            client=httpx.AsyncClient(transport=mock_transport, base_url="http://ggg-mock"),
        )
        try:
            yield client
        finally:
            await client.aclose()

    app = create_app()
    app.dependency_overrides[app_deps.get_ggg_client] = _ggg_client_override

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://testserver", follow_redirects=False
    ) as client:
        yield app, client, mock_app


async def _full_login(client: AsyncClient, mock_app) -> str:
    """Drive the whole OAuth2 dance, return the session cookie."""
    # 1. Start login: our backend redirects to the mock's /oauth/authorize.
    resp = await client.get("/api/auth/login")
    assert resp.status_code == 302
    authorize_url = resp.headers["location"]

    # 2. Hit the mock authorize page (GET) to create a pending request.
    mock_client = AsyncClient(transport=ASGITransport(app=mock_app), base_url="http://ggg-mock")
    from urllib.parse import urlparse

    parsed = urlparse(authorize_url)
    resp = await mock_client.get(parsed.path + "?" + parsed.query)
    assert resp.status_code == 200
    # Extract request_id from hidden input.
    import re

    match = re.search(r'name="request_id" value="([^"]+)"', resp.text)
    assert match, "no request_id in mock authorize page"
    request_id = match.group(1)

    # 3. Submit the form: mock redirects back to our callback with ?code&state
    resp = await mock_client.post(
        "/oauth/authorize",
        data={"request_id": request_id, "user": "exile_one"},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    callback_url = resp.headers["location"]
    assert "/api/auth/callback" in callback_url

    # 4. Hit our backend callback. It will exchange the code via the overridden
    #    GGG client (transport-routed to the same mock_app).
    cb_path = callback_url[callback_url.index("/api/auth/callback") :]
    await mock_client.aclose()
    resp = await client.get(cb_path)
    assert resp.status_code == 302, resp.text
    assert client.cookies.get("poe2b_session"), "no session cookie set"
    return client.cookies["poe2b_session"]


async def test_full_login_flow_sets_session_and_exposes_me(app_stack) -> None:
    _app, client, mock_app = app_stack
    await _full_login(client, mock_app)
    resp = await client.get("/api/me")
    assert resp.status_code == 200
    body = resp.json()
    assert body["account_name"] == "ExileOne#1234"


async def test_characters_endpoint_after_login(app_stack) -> None:
    _app, client, mock_app = app_stack
    await _full_login(client, mock_app)
    resp = await client.get("/api/characters")
    assert resp.status_code == 200
    data = resp.json()
    names = [c["name"] for c in data["characters"]]
    assert "Pewpewer" in names
    assert "Necroqueen" in names


async def test_refresh_requires_csrf(app_stack) -> None:
    _app, client, mock_app = app_stack
    await _full_login(client, mock_app)
    # No CSRF header -> 403
    resp = await client.post("/api/refresh")
    assert resp.status_code == 403

    # With valid CSRF -> 200
    csrf = client.cookies.get("poe2b_csrf")
    assert csrf
    resp = await client.post("/api/refresh", headers={"X-CSRF-Token": csrf})
    assert resp.status_code == 200, resp.text


async def test_refresh_cooldown_enforced(app_stack) -> None:
    _app, client, mock_app = app_stack
    await _full_login(client, mock_app)
    csrf = client.cookies.get("poe2b_csrf")
    resp1 = await client.post("/api/refresh", headers={"X-CSRF-Token": csrf})
    assert resp1.status_code == 200
    resp2 = await client.post("/api/refresh", headers={"X-CSRF-Token": csrf})
    assert resp2.status_code == 429
    assert "Retry-After" in resp2.headers


async def test_logout_clears_cookie_and_session(app_stack) -> None:
    _app, client, mock_app = app_stack
    await _full_login(client, mock_app)
    csrf = client.cookies.get("poe2b_csrf")
    resp = await client.post("/api/auth/logout", headers={"X-CSRF-Token": csrf})
    assert resp.status_code == 200
    # The cookie should be cleared; subsequent /api/me -> 401.
    client.cookies.clear()
    resp = await client.get("/api/me")
    assert resp.status_code == 401


async def test_trade_search_returns_payload_and_url(app_stack) -> None:
    _app, client, mock_app = app_stack
    await _full_login(client, mock_app)
    item = {
        "id": "i",
        "inventory_id": "Weapon",
        "w": 2,
        "h": 4,
        "x": None,
        "y": None,
        "name": "Doom Horn",
        "type_line": "Spine Bow",
        "base_type": "Spine Bow",
        "rarity": "Rare",
        "ilvl": 82,
        "identified": True,
        "corrupted": False,
        "properties": [],
        "requirements": [],
        "implicit_mods": [],
        "explicit_mods": ["+100 to maximum Life"],
        "rune_mods": [],
        "enchant_mods": [],
        "crafted_mods": [],
        "sockets": [],
        "stack_size": None,
        "max_stack_size": None,
        "icon": None,
    }
    resp = await client.post(
        "/api/trade/search",
        json={"mode": "exact", "item": item, "league": "Dawn of the Hunt"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["mode"] == "exact"
    assert body["url"].endswith("Dawn%20of%20the%20Hunt")
    assert body["payload"]["query"]["stats"][0]["filters"][0]["value"] == {
        "min": 90,
        "max": 110,
    }


async def test_prefs_patch_updates_tolerance_and_threshold(app_stack) -> None:
    _app, client, mock_app = app_stack
    await _full_login(client, mock_app)
    csrf = client.cookies.get("poe2b_csrf")

    resp = await client.request(
        "PATCH",
        "/api/prefs",
        json={"trade_tolerance_pct": 25, "valuable_threshold_chaos": 250},
        headers={"X-CSRF-Token": csrf},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["trade_tolerance_pct"] == 25
    assert body["valuable_threshold_chaos"] == 250

    resp = await client.get("/api/prefs")
    body = resp.json()
    assert body["trade_tolerance_pct"] == 25
    assert body["valuable_threshold_chaos"] == 250


async def test_pricing_lookup_returns_estimates_for_known_items(app_stack) -> None:
    _app, client, mock_app = app_stack
    await _full_login(client, mock_app)
    items = [
        {
            "id": "c1",
            "inventory_id": "Stash1",
            "w": 1,
            "h": 1,
            "x": 0,
            "y": 0,
            "name": "",
            "type_line": "Divine Orb",
            "base_type": "Divine Orb",
            "rarity": "Currency",
            "ilvl": None,
            "identified": True,
            "corrupted": False,
            "properties": [],
            "requirements": [],
            "implicit_mods": [],
            "explicit_mods": [],
            "rune_mods": [],
            "enchant_mods": [],
            "crafted_mods": [],
            "sockets": [],
            "stack_size": 1,
            "max_stack_size": 10,
            "icon": None,
        },
        {
            "id": "c2",
            "inventory_id": "Stash1",
            "w": 1,
            "h": 1,
            "x": 1,
            "y": 0,
            "name": "",
            "type_line": "Unknown Orb",
            "base_type": "Unknown Orb",
            "rarity": "Currency",
            "ilvl": None,
            "identified": True,
            "corrupted": False,
            "properties": [],
            "requirements": [],
            "implicit_mods": [],
            "explicit_mods": [],
            "rune_mods": [],
            "enchant_mods": [],
            "crafted_mods": [],
            "sockets": [],
            "stack_size": 1,
            "max_stack_size": 10,
            "icon": None,
        },
    ]
    resp = await client.post(
        "/api/pricing/lookup",
        json={"league": "Dawn of the Hunt", "items": items},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["prices"]["c1"]["chaos_equiv"] == 180.0
    assert body["prices"]["c2"] is None


async def test_stash_refresh_and_list(app_stack) -> None:
    _app, client, mock_app = app_stack
    await _full_login(client, mock_app)
    csrf = client.cookies.get("poe2b_csrf")

    resp = await client.post(
        "/api/stashes/refresh",
        json={"league": "Dawn of the Hunt"},
        headers={"X-CSRF-Token": csrf},
    )
    assert resp.status_code == 200, resp.text

    resp = await client.get("/api/stashes", params={"league": "Dawn of the Hunt"})
    assert resp.status_code == 200
    body = resp.json()
    names = [t["name"] for t in body["tabs"]]
    assert "Gear Dump" in names
    assert "Currency" in names

    tab_id = body["tabs"][0]["id"]
    resp = await client.get(f"/api/stashes/{tab_id}", params={"league": "Dawn of the Hunt"})
    assert resp.status_code == 200
    tab = resp.json()
    assert tab["tab"]["name"] == "Gear Dump"
    assert tab["items"][0]["name"] == "Agony Beads"


# Silence unused-import warnings from lint when these aren't referenced directly.
_ = os
