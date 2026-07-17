"""Tests for the API key system (Phase 1 — bot prerequisites).

Coverage:
- Key generation + verification roundtrip
- CRUD endpoints (create, get status, revoke) via session+CSRF
- Bearer auth on GET and POST routes
- CSRF bypass for Bearer auth on mutation routes
- Session auth still works on the same routes
- Rate limit (mock Redis counter)
- Admin revoke endpoint
- One active key per user policy
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from app.security.api_keys import extract_prefix, generate_api_key, verify_api_key

# Capture the original get_settings function before any fixture can monkeypatch it.
# This is needed so dependency_overrides uses the same function reference that
# admin_ops.py stored in its Depends(get_settings) at import time.
from app.config import get_settings as _ORIGINAL_GET_SETTINGS

# ── Unit tests: security module ───────────────────────────────────────────────


def test_generate_and_verify_roundtrip():
    secret = "test-secret"
    full_key, prefix, key_hash = generate_api_key(secret)
    assert full_key.startswith("hob_")
    assert prefix in full_key
    assert verify_api_key(full_key, key_hash, secret)


def test_verify_wrong_key_fails():
    secret = "test-secret"
    _, _, key_hash = generate_api_key(secret)
    assert not verify_api_key("hob_wrongprefix_wrongsecret1234567890abcdef", key_hash, secret)


def test_extract_prefix_valid():
    _, _, _ = generate_api_key("s")
    full_key = "hob_ABCDEFGHIJKL_ABCDEFGHIJKLMNOPQRSTUVWXYZ12"
    prefix = extract_prefix(full_key)
    assert prefix == "ABCDEFGHIJKL"


def test_extract_prefix_malformed():
    assert extract_prefix("not_a_valid_key") is None
    assert extract_prefix("hob_short") is None
    assert extract_prefix("") is None


def test_verify_different_pepper_fails():
    full_key, _, key_hash = generate_api_key("pepper-a")
    assert not verify_api_key(full_key, key_hash, "pepper-b")


# ── Integration tests: API key CRUD ──────────────────────────────────────────


async def test_create_api_key_returns_full_key(app_stack) -> None:
    _app, client, mock_app = app_stack
    # Must be logged in first.
    from tests.test_auth_flow import _full_login

    await _full_login(client, mock_app)
    csrf = client.cookies.get("poe2b_csrf")
    assert csrf

    resp = await client.post("/api/me/api-key", headers={"X-CSRF-Token": csrf})
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert "full_key" in body
    assert body["full_key"].startswith("hob_")
    assert "prefix" in body
    # Full key must not appear in subsequent status call.


async def test_get_api_key_status_no_secret(app_stack) -> None:
    _app, client, mock_app = app_stack
    from tests.test_auth_flow import _full_login

    await _full_login(client, mock_app)
    csrf = client.cookies.get("poe2b_csrf")

    # Create one first.
    create_resp = await client.post("/api/me/api-key", headers={"X-CSRF-Token": csrf})
    assert create_resp.status_code == 201
    prefix = create_resp.json()["prefix"]

    status_resp = await client.get("/api/me/api-key")
    assert status_resp.status_code == 200
    body = status_resp.json()
    assert body["prefix"] == prefix
    assert "full_key" not in body


async def test_revoke_api_key(app_stack) -> None:
    _app, client, mock_app = app_stack
    from tests.test_auth_flow import _full_login

    await _full_login(client, mock_app)
    csrf = client.cookies.get("poe2b_csrf")

    await client.post("/api/me/api-key", headers={"X-CSRF-Token": csrf})
    resp = await client.delete("/api/me/api-key", headers={"X-CSRF-Token": csrf})
    assert resp.status_code == 204

    # Status endpoint returns 404 after revoke.
    status_resp = await client.get("/api/me/api-key")
    assert status_resp.status_code == 404


async def test_create_key_revokes_existing(app_stack) -> None:
    _app, client, mock_app = app_stack
    from tests.test_auth_flow import _full_login

    await _full_login(client, mock_app)
    csrf = client.cookies.get("poe2b_csrf")

    first = await client.post("/api/me/api-key", headers={"X-CSRF-Token": csrf})
    assert first.status_code == 201
    first_prefix = first.json()["prefix"]

    second = await client.post("/api/me/api-key", headers={"X-CSRF-Token": csrf})
    assert second.status_code == 201
    second_prefix = second.json()["prefix"]

    assert first_prefix != second_prefix

    # Only the second key is active.
    status = await client.get("/api/me/api-key")
    assert status.json()["prefix"] == second_prefix


async def test_get_key_status_no_key_returns_404(app_stack) -> None:
    _app, client, mock_app = app_stack
    from tests.test_auth_flow import _full_login

    await _full_login(client, mock_app)
    resp = await client.get("/api/me/api-key")
    assert resp.status_code == 404


# ── Integration tests: Bearer auth on GET routes ──────────────────────────────


async def test_bearer_auth_on_me_endpoint(app_stack) -> None:
    _app, client, mock_app = app_stack
    from tests.test_auth_flow import _full_login
    from httpx import AsyncClient, ASGITransport

    await _full_login(client, mock_app)
    csrf = client.cookies.get("poe2b_csrf")

    create_resp = await client.post("/api/me/api-key", headers={"X-CSRF-Token": csrf})
    full_key = create_resp.json()["full_key"]

    # New client with no cookies — uses Bearer only.
    transport = client._transport
    api_client = AsyncClient(
        transport=transport, base_url="http://testserver", follow_redirects=False
    )
    resp = await api_client.get("/api/me", headers={"Authorization": f"Bearer {full_key}"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["account_name"] == "dominee_9275"
    await api_client.aclose()


async def test_bearer_invalid_key_rejected(app_stack) -> None:
    _app, client, mock_app = app_stack
    from tests.test_auth_flow import _full_login
    from httpx import AsyncClient

    await _full_login(client, mock_app)

    api_client = AsyncClient(
        transport=client._transport, base_url="http://testserver", follow_redirects=False
    )
    resp = await api_client.get(
        "/api/me", headers={"Authorization": "Bearer hob_badprefix12_badsecretbadsecretbadsecret12"}
    )
    assert resp.status_code == 401
    await api_client.aclose()


async def test_bearer_revoked_key_rejected(app_stack) -> None:
    _app, client, mock_app = app_stack
    from tests.test_auth_flow import _full_login
    from httpx import AsyncClient

    await _full_login(client, mock_app)
    csrf = client.cookies.get("poe2b_csrf")

    create_resp = await client.post("/api/me/api-key", headers={"X-CSRF-Token": csrf})
    full_key = create_resp.json()["full_key"]

    # Revoke it.
    await client.delete("/api/me/api-key", headers={"X-CSRF-Token": csrf})

    api_client = AsyncClient(
        transport=client._transport, base_url="http://testserver", follow_redirects=False
    )
    resp = await api_client.get("/api/me", headers={"Authorization": f"Bearer {full_key}"})
    assert resp.status_code == 401
    await api_client.aclose()


# ── Integration tests: Bearer auth on mutation routes (no CSRF needed) ────────


async def test_bearer_can_call_refresh_without_csrf(app_stack) -> None:
    _app, client, mock_app = app_stack
    from tests.test_auth_flow import _full_login
    from httpx import AsyncClient

    await _full_login(client, mock_app)
    csrf = client.cookies.get("poe2b_csrf")

    create_resp = await client.post("/api/me/api-key", headers={"X-CSRF-Token": csrf})
    full_key = create_resp.json()["full_key"]

    api_client = AsyncClient(
        transport=client._transport, base_url="http://testserver", follow_redirects=False
    )
    # No X-CSRF-Token header — Bearer bypasses CSRF.
    resp = await api_client.post(
        "/api/refresh", headers={"Authorization": f"Bearer {full_key}"}
    )
    assert resp.status_code == 200, resp.text
    await api_client.aclose()


async def test_session_auth_still_works_on_bearer_routes(app_stack) -> None:
    _app, client, mock_app = app_stack
    from tests.test_auth_flow import _full_login

    await _full_login(client, mock_app)
    resp = await client.get("/api/me")
    assert resp.status_code == 200


async def test_csrf_required_for_session_mutation(app_stack) -> None:
    _app, client, mock_app = app_stack
    from tests.test_auth_flow import _full_login

    await _full_login(client, mock_app)
    # Session client without CSRF header should get 403 on mutations.
    resp = await client.post("/api/refresh")
    assert resp.status_code == 403


# ── Integration tests: rate limit (mock) ─────────────────────────────────────


async def test_rate_limit_exceeded_returns_429(app_stack, monkeypatch) -> None:
    """When the rate limit service raises 429, the endpoint propagates it."""
    from app import deps as app_deps
    from fastapi import HTTPException

    async def _always_429(redis, prefix, limit):
        raise HTTPException(status_code=429, detail="api_key_rate_limited")

    monkeypatch.setattr(app_deps._api_key_ratelimit_mod, "enforce_api_key_rate_limit", _always_429)

    _app, client, mock_app = app_stack
    from tests.test_auth_flow import _full_login
    from httpx import AsyncClient

    await _full_login(client, mock_app)
    csrf = client.cookies.get("poe2b_csrf")
    create_resp = await client.post("/api/me/api-key", headers={"X-CSRF-Token": csrf})
    full_key = create_resp.json()["full_key"]

    api_client = AsyncClient(
        transport=client._transport, base_url="http://testserver", follow_redirects=False
    )
    resp = await api_client.get("/api/me", headers={"Authorization": f"Bearer {full_key}"})
    assert resp.status_code == 429
    await api_client.aclose()


# ── Integration tests: admin revoke ──────────────────────────────────────────


async def test_admin_revoke_api_key(app_stack) -> None:
    _app, client, mock_app = app_stack
    from tests.test_auth_flow import _full_login
    from app import config as app_config
    from pydantic import SecretStr

    await _full_login(client, mock_app)
    csrf = client.cookies.get("poe2b_csrf")

    create_resp = await client.post("/api/me/api-key", headers={"X-CSRF-Token": csrf})
    assert create_resp.status_code == 201
    full_key = create_resp.json()["full_key"]

    # Use FastAPI's dependency override with the ORIGINAL function (captured at module level
    # before any fixtures monkeypatch it) so the override key matches what admin_ops.py stored.
    base_settings = app_config.get_settings()
    patched = base_settings.model_copy(
        update={"admin_internal_secret": SecretStr("test-admin-secret")}
    )
    _app.dependency_overrides[_ORIGINAL_GET_SETTINGS] = lambda: patched

    try:
        me_resp = await client.get("/api/me")
        user_id = me_resp.json()["id"]

        revoke_resp = await client.post(
            f"/api/admin/users/{user_id}/api-key/revoke",
            headers={"X-Admin-Internal-Secret": "test-admin-secret"},
        )
        assert revoke_resp.status_code == 200, revoke_resp.text
        assert revoke_resp.json()["ok"] is True
    finally:
        del _app.dependency_overrides[_ORIGINAL_GET_SETTINGS]

    # Key no longer works.
    from httpx import AsyncClient

    api_client = AsyncClient(
        transport=client._transport, base_url="http://testserver", follow_redirects=False
    )
    resp = await api_client.get("/api/me", headers={"Authorization": f"Bearer {full_key}"})
    assert resp.status_code == 401
    await api_client.aclose()


async def test_admin_revoke_api_key_no_key_returns_ok(app_stack) -> None:
    _app, client, mock_app = app_stack
    from tests.test_auth_flow import _full_login
    from app import config as app_config
    from pydantic import SecretStr

    await _full_login(client, mock_app)

    base_settings = app_config.get_settings()
    patched = base_settings.model_copy(
        update={"admin_internal_secret": SecretStr("test-admin-secret")}
    )
    _app.dependency_overrides[_ORIGINAL_GET_SETTINGS] = lambda: patched

    try:
        me_resp = await client.get("/api/me")
        user_id = me_resp.json()["id"]

        resp = await client.post(
            f"/api/admin/users/{user_id}/api-key/revoke",
            headers={"X-Admin-Internal-Secret": "test-admin-secret"},
        )
        assert resp.status_code == 200
        assert resp.json()["detail"] == "no_active_key"
    finally:
        del _app.dependency_overrides[_ORIGINAL_GET_SETTINGS]


# ── Integration tests: prefs with preferred_character_name ────────────────────


async def test_prefs_set_preferred_character(app_stack) -> None:
    _app, client, mock_app = app_stack
    from tests.test_auth_flow import _full_login

    await _full_login(client, mock_app)
    csrf = client.cookies.get("poe2b_csrf")

    resp = await client.request(
        "PATCH",
        "/api/prefs",
        json={"preferred_character_name": "OracleElevenG"},
        headers={"X-CSRF-Token": csrf},
    )
    assert resp.status_code == 200
    assert resp.json()["preferred_character_name"] == "OracleElevenG"

    # Persisted.
    get_resp = await client.get("/api/prefs")
    assert get_resp.json()["preferred_character_name"] == "OracleElevenG"


async def test_prefs_set_preferred_character_via_bearer(app_stack) -> None:
    _app, client, mock_app = app_stack
    from tests.test_auth_flow import _full_login
    from httpx import AsyncClient

    await _full_login(client, mock_app)
    csrf = client.cookies.get("poe2b_csrf")
    create_resp = await client.post("/api/me/api-key", headers={"X-CSRF-Token": csrf})
    full_key = create_resp.json()["full_key"]

    api_client = AsyncClient(
        transport=client._transport, base_url="http://testserver", follow_redirects=False
    )
    resp = await api_client.request(
        "PATCH",
        "/api/prefs",
        json={"preferred_character_name": "BringTheRainz"},
        headers={"Authorization": f"Bearer {full_key}", "Content-Type": "application/json"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["preferred_character_name"] == "BringTheRainz"
    await api_client.aclose()
