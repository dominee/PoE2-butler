"""Live integration tests for GGG OAuth2 and API endpoints.

These tests are skipped by default and must be run explicitly with the
``live_ggg`` marker after the UAT stack is up with real credentials:

    uv run pytest -m live_ggg -v

Required env vars (set in .env.uat or exported):
    GGG_CLIENT_ID          — real GGG client id
    GGG_CLIENT_SECRET      — real GGG client secret
    GGG_OAUTH_BASE_URL     — https://www.pathofexile.com
    GGG_API_BASE_URL       — https://api.pathofexile.com
    GGG_REDIRECT_URI       — https://app.uat.hideoutbutler.com/api/auth/callback
    GGG_SCOPES             — account:profile account:characters

Optional (for full round-trip token test):
    GGG_TEST_REFRESH_TOKEN — a valid refresh token obtained via a prior login;
                             without this, token-dependent tests are skipped.
"""

from __future__ import annotations

import os

import httpx
import pytest

pytestmark = pytest.mark.live_ggg

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_REAL_GGG_OAUTH = "www.pathofexile.com"
_REAL_GGG_API = "api.pathofexile.com"


def _settings() -> dict[str, str]:
    return {
        "oauth_base": os.environ.get("GGG_OAUTH_BASE_URL", ""),
        "api_base": os.environ.get("GGG_API_BASE_URL", ""),
        "client_id": os.environ.get("GGG_CLIENT_ID", ""),
        "client_secret": os.environ.get("GGG_CLIENT_SECRET", ""),
        "redirect_uri": os.environ.get("GGG_REDIRECT_URI", ""),
        "scopes": os.environ.get("GGG_SCOPES", ""),
    }


def _ua(client_id: str) -> str:
    return f"OAuth {client_id}/test (contact: dev@hell.sk) PoE2-Hideout-Butler"


# ---------------------------------------------------------------------------
# Configuration validation (no network calls)
# ---------------------------------------------------------------------------


def test_live_ggg_urls_configured() -> None:
    """GGG_OAUTH_BASE_URL and GGG_API_BASE_URL must point to real GGG."""
    s = _settings()
    assert _REAL_GGG_OAUTH in s["oauth_base"], (
        f"GGG_OAUTH_BASE_URL={s['oauth_base']!r} does not look like real GGG. "
        f"Expected a URL containing '{_REAL_GGG_OAUTH}'."
    )
    assert _REAL_GGG_API in s["api_base"], (
        f"GGG_API_BASE_URL={s['api_base']!r} does not look like real GGG API. "
        f"Expected a URL containing '{_REAL_GGG_API}'."
    )


def test_client_id_not_placeholder() -> None:
    """GGG_CLIENT_ID must not be the dev placeholder."""
    client_id = _settings()["client_id"]
    assert client_id, "GGG_CLIENT_ID is not set."
    assert client_id != "poe2-butler-dev", (
        "GGG_CLIENT_ID is still the dev placeholder. Set the real GGG client id."
    )


def test_scopes_match_granted() -> None:
    """GGG_SCOPES must only contain the scopes that were granted."""
    scopes = set(_settings()["scopes"].split())
    granted = {"account:profile", "account:characters"}
    not_granted = {"account:stashes", "account:leagues"}
    unexpected = scopes & not_granted
    assert not unexpected, (
        f"GGG_SCOPES contains scope(s) not granted by GGG: {unexpected}. "
        "Requesting undeclared scopes will cause the authorization to fail."
    )
    assert scopes >= granted, (
        f"GGG_SCOPES is missing expected scopes: {granted - scopes}"
    )


def test_redirect_uri_is_uat() -> None:
    """GGG_REDIRECT_URI must be the registered UAT URI."""
    uri = _settings()["redirect_uri"]
    assert uri, "GGG_REDIRECT_URI is not set."
    assert "hideoutbutler.com" in uri, (
        f"GGG_REDIRECT_URI={uri!r} does not contain 'hideoutbutler.com'."
    )
    assert uri.startswith("https://"), (
        f"GGG_REDIRECT_URI={uri!r} must use HTTPS (required for live GGG)."
    )


def test_authorize_url_format() -> None:
    """The generated authorization URL must contain the expected parameters."""
    import hashlib
    from base64 import urlsafe_b64encode
    from urllib.parse import parse_qs, urlencode, urlparse

    s = _settings()
    challenge = (
        urlsafe_b64encode(hashlib.sha256(b"test-verifier").digest()).rstrip(b"=").decode()
    )
    params = {
        "client_id": s["client_id"],
        "response_type": "code",
        "scope": s["scopes"],
        "state": "test-state",
        "redirect_uri": s["redirect_uri"],
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    base = s["oauth_base"].rstrip("/")
    url = f"{base}/oauth/authorize?{urlencode(params)}"
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)

    assert qs["client_id"] == [s["client_id"]]
    assert qs["response_type"] == ["code"]
    assert qs["code_challenge_method"] == ["S256"]
    assert qs["redirect_uri"] == [s["redirect_uri"]]
    assert parsed.scheme == "https"
    assert _REAL_GGG_OAUTH in parsed.netloc


# ---------------------------------------------------------------------------
# Network probes
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ggg_token_endpoint_reachable() -> None:
    """The GGG token endpoint must respond (405 or 400 are fine; 000 is not)."""
    oauth_base = _settings()["oauth_base"]
    url = f"{oauth_base.rstrip('/')}/oauth/token"
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.head(url)
    # GGG returns 405 for HEAD on the token endpoint; any HTTP response is acceptable.
    assert r.status_code > 0, f"No HTTP response from {url}"
    assert r.status_code not in (0, 502, 503, 504), (
        f"GGG token endpoint returned unexpected status {r.status_code}"
    )


@pytest.mark.asyncio
async def test_ggg_profile_endpoint_reachable_without_token() -> None:
    """The GGG /profile endpoint must return 401 when called without a token."""
    s = _settings()
    url = f"{s['api_base'].rstrip('/')}/profile"
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.get(url, headers={"User-Agent": _ua(s["client_id"])})
    assert r.status_code == 401, (
        f"Expected 401 Unauthorized from {url}, got {r.status_code}. "
        "Check that GGG_API_BASE_URL points to the real GGG API."
    )


# ---------------------------------------------------------------------------
# Full round-trip (requires GGG_TEST_REFRESH_TOKEN in env)
# ---------------------------------------------------------------------------


@pytest.fixture
def refresh_token() -> str:
    token = os.environ.get("GGG_TEST_REFRESH_TOKEN", "")
    if not token:
        pytest.skip("GGG_TEST_REFRESH_TOKEN not set — skipping token round-trip test.")
    return token


@pytest.mark.asyncio
async def test_refresh_token_exchange(refresh_token: str) -> None:
    """Exchange a refresh token for a new access token and call /profile."""
    s = _settings()
    token_url = f"{s['oauth_base'].rstrip('/')}/oauth/token"

    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.post(
            token_url,
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": s["client_id"],
                "client_secret": s["client_secret"],
            },
            headers={"User-Agent": _ua(s["client_id"])},
        )
        assert r.status_code == 200, (
            f"Token refresh failed: HTTP {r.status_code} — {r.text[:300]}"
        )
        body = r.json()
        access_token = body.get("access_token", "")
        assert access_token, "No access_token in refresh response."
        scopes = body.get("scope", "")
        assert "account:profile" in scopes, f"account:profile not in granted scopes: {scopes!r}"

        # Call /profile with the fresh access token.
        profile_url = f"{s['api_base'].rstrip('/')}/profile"
        rp = await client.get(
            profile_url,
            headers={
                "Authorization": f"Bearer {access_token}",
                "User-Agent": _ua(s["client_id"]),
            },
        )
        assert rp.status_code == 200, (
            f"GET /profile failed: HTTP {rp.status_code} — {rp.text[:300]}"
        )
        profile = rp.json()
        account_name = profile.get("name") or profile.get("uuid") or ""
        assert account_name, f"No account name in /profile response: {profile}"


@pytest.mark.asyncio
async def test_characters_with_refresh_token(refresh_token: str) -> None:
    """Exchange a refresh token and call /account/characters."""
    s = _settings()
    token_url = f"{s['oauth_base'].rstrip('/')}/oauth/token"

    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.post(
            token_url,
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": s["client_id"],
                "client_secret": s["client_secret"],
            },
            headers={"User-Agent": _ua(s["client_id"])},
        )
        assert r.status_code == 200
        access_token = r.json().get("access_token", "")
        assert access_token

        chars_url = f"{s['api_base'].rstrip('/')}/account/characters"
        rc = await client.get(
            chars_url,
            headers={
                "Authorization": f"Bearer {access_token}",
                "User-Agent": _ua(s["client_id"]),
            },
        )
        assert rc.status_code == 200, (
            f"GET /account/characters failed: HTTP {rc.status_code} — {rc.text[:300]}"
        )
        data = rc.json()
        characters = data.get("characters") or []
        assert isinstance(characters, list), f"Unexpected /account/characters shape: {data!r}"
