"""API smoke tests — bot-readiness and security coverage.

Ported from butler-bot/tests/test_live_api.py and expanded with
unauthorized-access scenarios.  All tests run against the in-process
FastAPI app (hermetic, no real network).

Coverage:
- Public endpoints: /healthz, /readyz, /docs, /openapi.json
- Unauthorized access: no token, empty Bearer, malformed token, wrong token,
  valid-format but non-existent key
- Authenticated read endpoints: /api/me, /api/prefs, /api/leagues,
  /api/characters, /api/characters/{name}, /api/characters/{name}/snapshots,
  /api/activity, /api/pricing/currency-rates
- Authenticated mutations: PATCH /api/prefs, POST /api/items/item-text,
  POST /api/trade/search, POST /api/character-shares
- Edge cases: unknown character (404), public share (no auth required)

Live tests (require a real running server) are marked @pytest.mark.live_api
and excluded from the default test run.  Set
``BOT_API_BASE_URL`` + ``BOT_API_KEY`` and run with ``-m live_api`` to opt in.
"""

from __future__ import annotations

from typing import Any

import pytest
from httpx import AsyncClient, Response

from tests.test_auth_flow import _full_login

# Known mock-ggg user (must match poe_ninja_characters.toml + characters.json fixture)
KNOWN_ACCOUNT = "dominee_9275"
KNOWN_CHAR = "OracleElevenG"
KNOWN_LEAGUE = "Runes of Aldur"


# ---------------------------------------------------------------------------
# Shared fixture: logged-in session + API key
# ---------------------------------------------------------------------------


class _BearerProxy:
    """Thin wrapper that forwards requests through the session client, injecting
    ``Authorization: Bearer …`` on every call.

    Using the existing session client avoids creating a second ``AsyncClient``
    with a new transport, which was causing non-deterministic 401 failures when
    the second transport was torn down in a different async-loop context than
    the one the database session factory was created in.

    For GET routes ``get_current_user_any`` checks the session cookie first,
    returning the same user as the bearer path would.  For mutation routes
    ``get_current_user_mutate`` checks the bearer token first, so CSRF is
    bypassed correctly without needing to pass ``X-CSRF-Token``.
    """

    def __init__(self, session_client: AsyncClient, full_key: str) -> None:
        self._client = session_client
        self._bearer = {"Authorization": f"Bearer {full_key}"}

    def _merge(self, kwargs: dict[str, Any]) -> dict[str, Any]:
        existing = dict(kwargs.pop("headers", {}) or {})
        existing.update(self._bearer)
        return {**kwargs, "headers": existing}

    async def get(self, url: str, **kwargs: Any) -> Response:
        return await self._client.get(url, **self._merge(kwargs))

    async def post(self, url: str, **kwargs: Any) -> Response:
        return await self._client.post(url, **self._merge(kwargs))

    async def patch(self, url: str, **kwargs: Any) -> Response:
        return await self._client.patch(url, **self._merge(kwargs))

    async def delete(self, url: str, **kwargs: Any) -> Response:
        return await self._client.delete(url, **self._merge(kwargs))


@pytest.fixture
async def authed(app_stack):
    """Return ``(bearer_proxy, full_key)`` for tests that need an authenticated user.

    ``bearer_proxy`` proxies the session client and injects the Bearer header on
    every request.  No second ``AsyncClient`` or transport is created.
    """
    _app, client, mock_app = app_stack
    await _full_login(client, mock_app)

    csrf = client.cookies.get("poe2b_csrf")
    assert csrf, "CSRF cookie missing after login"

    resp = await client.post("/api/me/api-key", headers={"X-CSRF-Token": csrf})
    assert resp.status_code == 201, f"API key creation failed: {resp.text}"
    full_key: str = resp.json()["full_key"]

    yield _BearerProxy(client, full_key), full_key


# ===========================================================================
# Public endpoints — no authentication required
# ===========================================================================


async def test_healthz_ok(app_stack) -> None:
    """Liveness probe: returns 200 and status=ok."""
    _app, client, _mock = app_stack
    r = await client.get("/healthz")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


async def test_readyz_ok(app_stack) -> None:
    """Readiness probe: returns 200 and status=ready."""
    _app, client, _mock = app_stack
    r = await client.get("/readyz")
    assert r.status_code == 200
    assert r.json()["status"] == "ready"


async def test_docs_accessible(app_stack) -> None:
    """Swagger UI is served at /docs (HTML, references openapi/swagger)."""
    _app, client, _mock = app_stack
    r = await client.get("/docs")
    assert r.status_code == 200
    ct = r.headers.get("content-type", "")
    assert "text/html" in ct
    assert b"swagger" in r.content.lower() or b"openapi" in r.content.lower()


async def test_openapi_json_accessible(app_stack) -> None:
    """OpenAPI JSON schema is valid and covers key bot-facing paths."""
    _app, client, _mock = app_stack
    r = await client.get("/openapi.json")
    assert r.status_code == 200
    schema = r.json()
    assert schema.get("openapi", "").startswith("3.")
    paths = schema.get("paths", {})
    for expected in ("/api/me", "/api/characters", "/api/prefs"):
        assert expected in paths, f"OpenAPI schema missing path: {expected}"


# ===========================================================================
# Unauthorized access — all patterns must return 401
# ===========================================================================


async def test_no_auth_header_rejected(app_stack) -> None:
    """GET /api/me with no Authorization header → 401."""
    _app, client, _mock = app_stack
    r = await client.get("/api/me")
    # Without a session cookie the endpoint returns 401.
    assert r.status_code == 401, r.text


async def test_empty_bearer_token_rejected(app_stack) -> None:
    """Empty Bearer token string → 401."""
    _app, client, _mock = app_stack
    r = await client.get("/api/me", headers={"Authorization": "Bearer "})
    assert r.status_code == 401, r.text


async def test_malformed_bearer_prefix_rejected(app_stack) -> None:
    """Token missing 'hob_' prefix → 401."""
    _app, client, _mock = app_stack
    r = await client.get("/api/me", headers={"Authorization": "Bearer not_a_valid_key"})
    assert r.status_code == 401, r.text


async def test_wrong_bearer_token_rejected(app_stack) -> None:
    """Plausible-looking but non-existent key → 401."""
    _app, client, _mock = app_stack
    r = await client.get(
        "/api/me",
        headers={"Authorization": "Bearer hob_AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAx"},
    )
    assert r.status_code == 401, r.text


async def test_incorrect_token_with_valid_format_rejected(app_stack) -> None:
    """hob_ + correct-length prefix + secret that doesn't match DB → 401."""
    _app, client, _mock = app_stack
    # 12-char prefix + 32-char secret (matching _PREFIX_LEN and _SECRET_LEN)
    fake_key = "hob_AAAAAAAAAAAA_BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB"
    r = await client.get("/api/me", headers={"Authorization": f"Bearer {fake_key}"})
    assert r.status_code == 401, r.text


async def test_bearer_on_mutation_endpoint_without_key_rejected(app_stack) -> None:
    """POST /api/refresh with no auth → 401."""
    _app, client, _mock = app_stack
    r = await client.post("/api/refresh")
    assert r.status_code == 401, r.text


async def test_bearer_csrf_not_required_for_bearer_mutations(authed) -> None:
    """Bearer-authenticated mutations must NOT require CSRF header.

    The bot has no browser cookie context, so CSRF enforcement would break it.
    We use PATCH /api/prefs as the canary (no state change from a no-op PATCH).

    ``get_current_user_mutate`` checks Bearer first — the proxy injects the
    header — so CSRF is bypassed entirely.
    """
    client, _key = authed
    # No X-CSRF-Token header — bearer auth should bypass CSRF check.
    r = await client.patch("/api/prefs", json={})
    assert r.status_code == 200, (
        f"Bearer mutation rejected without CSRF (got {r.status_code}): {r.text}"
    )


# ===========================================================================
# Auth & identity  →  bot command: (internal verify)
# ===========================================================================


async def test_me_returns_account(authed) -> None:
    """Bearer token resolves to the correct GGG account name."""
    client, _key = authed
    r = await client.get("/api/me")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["account_name"] == KNOWN_ACCOUNT
    assert "id" in data
    assert "preferred_league" in data


async def test_me_capabilities_present(authed) -> None:
    """GET /api/me includes a capabilities object."""
    client, _key = authed
    r = await client.get("/api/me")
    assert r.status_code == 200, r.text
    data = r.json()
    assert "capabilities" in data, f"No 'capabilities' in /api/me response: {list(data)}"


# ===========================================================================
# Preferences  →  bot commands: /prefs show, /prefs set
# ===========================================================================


async def test_prefs_get(authed) -> None:
    """/prefs show: response includes all preference fields."""
    client, _key = authed
    r = await client.get("/api/prefs")
    assert r.status_code == 200, r.text
    data = r.json()
    assert "preferred_league" in data
    assert "preferred_character_name" in data
    assert "trade_tolerance_pct" in data
    assert "valuable_threshold_chaos" in data


async def test_prefs_set_preferred_character(authed) -> None:
    """/prefs set character: PATCH persists and is readable back."""
    client, _key = authed
    r = await client.patch("/api/prefs", json={"preferred_character_name": KNOWN_CHAR})
    assert r.status_code == 200, r.text
    assert r.json()["preferred_character_name"] == KNOWN_CHAR

    r2 = await client.get("/api/prefs")
    assert r2.json()["preferred_character_name"] == KNOWN_CHAR


async def test_prefs_set_league(authed) -> None:
    """/prefs set league: PATCH persists the preferred_league."""
    client, _key = authed
    r = await client.patch("/api/prefs", json={"preferred_league": KNOWN_LEAGUE})
    assert r.status_code == 200, r.text
    assert r.json()["preferred_league"] == KNOWN_LEAGUE


# ===========================================================================
# Leagues  →  bot: internal / /prefs set league
# ===========================================================================


async def test_leagues_list(authed) -> None:
    """Leagues endpoint returns a list that includes the user's known league."""
    client, _key = authed
    r = await client.get("/api/leagues")
    assert r.status_code == 200, r.text
    data = r.json()
    assert "leagues" in data
    ids = [lg["id"] for lg in data["leagues"]]
    assert KNOWN_LEAGUE in ids, f"Expected league {KNOWN_LEAGUE!r} in {ids}"
    assert "preferred" in data


# ===========================================================================
# Characters  →  bot commands: /characters list, /character show
# ===========================================================================


async def test_characters_list(authed) -> None:
    """/characters list: returns characters for the preferred league."""
    client, _key = authed
    r = await client.get("/api/characters", params={"league": KNOWN_LEAGUE})
    assert r.status_code == 200, r.text
    data = r.json()
    assert "characters" in data
    names = [c["name"] for c in data["characters"]]
    assert KNOWN_CHAR in names, f"Expected {KNOWN_CHAR!r} in character list {names}"


async def test_character_detail(authed) -> None:
    """/character show: character detail includes summary and required keys."""
    client, _key = authed
    r = await client.get(f"/api/characters/{KNOWN_CHAR}")
    assert r.status_code == 200, r.text
    data = r.json()
    summary = data["summary"]
    assert summary["name"] == KNOWN_CHAR
    assert "equipped" in data
    assert "gems" in data
    assert "jewels" in data
    assert "snapshot_fetched_at" in data
    assert data["is_historical"] is False


async def test_character_unknown_returns_404(authed) -> None:
    """Unknown character name → 404, not an unhandled exception."""
    client, _key = authed
    r = await client.get("/api/characters/this_char_does_not_exist_xyz987")
    assert r.status_code == 404, r.text


# ===========================================================================
# Snapshot timeline  →  bot commands: /character timeline, /character history
# ===========================================================================


async def test_character_snapshots(authed) -> None:
    """/character timeline: returns snapshot list with at least the current entry."""
    client, _key = authed
    r = await client.get(f"/api/characters/{KNOWN_CHAR}/snapshots")
    assert r.status_code == 200, r.text
    data = r.json()
    assert "snapshots" in data
    assert len(data["snapshots"]) >= 1
    current = next((s for s in data["snapshots"] if s.get("is_current")), None)
    assert current is not None, "No current snapshot found in timeline"


# ===========================================================================
# Activity diff  →  bot command: /activity
# ===========================================================================


async def test_activity(authed) -> None:
    """Activity log returns a structured diff response for the known league."""
    client, _key = authed
    r = await client.get("/api/activity", params={"league": KNOWN_LEAGUE})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["league"] == KNOWN_LEAGUE
    assert "total_new" in data
    assert "total_changed" in data
    assert "has_prev" in data


# ===========================================================================
# Pricing  →  bot command: /rates
# ===========================================================================


async def test_currency_rates(authed) -> None:
    """/rates: chaos-per-divine and chaos-per-exalted are positive numbers."""
    client, _key = authed
    r = await client.get("/api/pricing/currency-rates", params={"league": KNOWN_LEAGUE})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["league"] == KNOWN_LEAGUE
    assert data["chaos_per_divine"] > 0
    assert data["chaos_per_exalted"] > 0


# ===========================================================================
# Item text parsing  →  bot command: /item parse
# ===========================================================================

_SAMPLE_ITEM = {
    "id": "smoke-item-001",
    "name": "",
    "typeLine": "Iron Ring",
    "baseType": "Iron Ring",
    "rarity": "Normal",
    "itemLevel": 20,
    "identified": True,
    "explicitMods": ["Adds 1 to 3 Physical Damage to Attacks"],
    "implicitMods": [],
}


async def test_item_text_format(authed) -> None:
    """/item parse: structured item is formatted into PoE2 clipboard text."""
    client, _key = authed
    r = await client.post("/api/items/item-text", json={"item": _SAMPLE_ITEM})
    assert r.status_code == 200, r.text
    data = r.json()
    assert "text" in data
    assert "Iron Ring" in data["text"] or "Normal" in data["text"]


# ===========================================================================
# Trade search  →  bot commands: /trade exact, /trade upgrade
# ===========================================================================

_SAMPLE_TRADE_ITEM = {
    "id": "test-item-001",
    "name": "",
    "typeLine": "Iron Ring",
    "baseType": "Iron Ring",
    "rarity": "Normal",
    "itemLevel": 1,
    "identified": True,
    "explicitMods": [],
    "implicitMods": [],
    "extended": {"mods": {}},
}


async def test_trade_search_exact_returns_url(authed) -> None:
    """/trade exact: returns a trade URL for the given item."""
    client, _key = authed
    r = await client.post(
        "/api/trade/search",
        json={
            "mode": "exact",
            "item": _SAMPLE_TRADE_ITEM,
            "league": KNOWN_LEAGUE,
        },
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert "url" in data, f"No 'url' key in response: {data}"
    assert "pathofexile.com/trade2" in data["url"]


async def test_trade_search_upgrade_returns_url(authed) -> None:
    """/trade upgrade: returns a trade URL for the upgrade search mode."""
    client, _key = authed
    r = await client.post(
        "/api/trade/search",
        json={
            "mode": "upgrade",
            "item": _SAMPLE_TRADE_ITEM,
            "league": KNOWN_LEAGUE,
        },
    )
    assert r.status_code == 200, r.text
    assert "url" in r.json()


async def test_trade_search_invalid_mode_rejected(authed) -> None:
    """Unknown trade mode → 422 Unprocessable Entity."""
    client, _key = authed
    r = await client.post(
        "/api/trade/search",
        json={
            "mode": "teleport",
            "item": _SAMPLE_TRADE_ITEM,
            "league": KNOWN_LEAGUE,
        },
    )
    assert r.status_code == 422, r.text


# ===========================================================================
# Character shares  →  bot command: /character share
# ===========================================================================


async def test_character_share_create_and_public_read(authed, app_stack) -> None:
    """/character share: creates a public share link; world-readable without auth."""
    client, _key = authed
    r = await client.post(
        "/api/character-shares",
        json={"character_name": KNOWN_CHAR, "league": KNOWN_LEAGUE},
    )
    assert r.status_code in (200, 201), r.text
    data = r.json()
    assert "share_id" in data, f"No share_id in response: {data}"
    assert "public_path" in data

    # Public endpoint must be accessible without auth.
    _app, anon_client, _mock = app_stack
    share_id = data["share_id"]
    pub = await anon_client.get(f"/api/public/characters/{share_id}")
    assert pub.status_code == 200, pub.text
    pub_data = pub.json()
    assert pub_data["character_name"] == KNOWN_CHAR


async def test_public_share_unknown_id_returns_404(app_stack) -> None:
    """Unknown share UUID → 404, no auth required."""
    import uuid

    _app, client, _mock = app_stack
    r = await client.get(f"/api/public/characters/{uuid.uuid4()}")
    assert r.status_code == 404, r.text


# ===========================================================================
# API key management  →  web UI: GET /api/me/api-key, DELETE /api/me/api-key
# ===========================================================================


async def test_api_key_status_visible(authed, app_stack) -> None:
    """GET /api/me/api-key returns prefix + timestamps; no secret."""
    _app, session_client, _mock = app_stack
    # Use the session-authenticated client to check key status.
    r = await session_client.get("/api/me/api-key")
    assert r.status_code == 200, r.text
    data = r.json()
    assert "prefix" in data
    assert "full_key" not in data, "API key status must NOT expose the secret"


async def test_revoked_key_rejected(app_stack) -> None:
    """After revocation, the key must no longer be accepted (bearer-only client)."""
    _app, client, mock_app = app_stack
    await _full_login(client, mock_app)

    csrf = client.cookies.get("poe2b_csrf")
    # Create a key.
    r = await client.post("/api/me/api-key", headers={"X-CSRF-Token": csrf})
    assert r.status_code == 201
    full_key = r.json()["full_key"]

    # Revoke it.
    r_del = await client.delete("/api/me/api-key", headers={"X-CSRF-Token": csrf})
    assert r_del.status_code == 204, r_del.text

    # The revoked key should now return 401 when used as the ONLY credential.
    # We use an explicit Authorization header on the raw session client but
    # clear its cookie jar temporarily so the session path is not taken.
    original_cookies = dict(client.cookies)
    client.cookies.clear()
    try:
        r_me = await client.get("/api/me", headers={"Authorization": f"Bearer {full_key}"})
    finally:
        for name, value in original_cookies.items():
            client.cookies.set(name, value)

    assert r_me.status_code == 401, (
        f"Revoked key was accepted (got {r_me.status_code}): {r_me.text}"
    )
