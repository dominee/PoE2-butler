from __future__ import annotations

import httpx
import pytest
from pydantic import SecretStr

from app.clients.ggg import GGGClient, GGGError, ggg_error_implies_reauth
from app.config import Settings


def _settings() -> Settings:
    return Settings(
        environment="test",
        ggg_oauth_base_url="http://ggg.test",
        ggg_api_base_url="http://ggg.test",
        ggg_client_id="mypoeapp",
        ggg_client_secret=SecretStr("test-secret"),
        ggg_redirect_uri="http://testserver/api/auth/callback",
        app_version="1.0.0",
        ggg_user_agent_contact="dev@hell.sk",
        ggg_user_agent_suffix="SomeOptionalThingHere",
    )


@pytest.mark.asyncio
async def test_ggg_client_sends_mandatory_user_agent_header() -> None:
    expected_user_agent = "OAuth mypoeapp/1.0.0 (contact: dev@hell.sk) SomeOptionalThingHere"

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers.get("User-Agent") == expected_user_agent
        if request.url.path == "/oauth/token":
            return httpx.Response(
                200,
                json={
                    "access_token": "token",
                    "refresh_token": "refresh",
                    "expires_in": 3600,
                    "scope": "account:profile",
                },
            )
        if request.url.path == "/profile":
            assert request.headers.get("Authorization") == "Bearer token"
            return httpx.Response(200, json={"name": "ExileOne#1234"})
        return httpx.Response(404, json={"detail": "not_found"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="http://ggg.test") as client:
        ggg = GGGClient(_settings(), client=client)
        await ggg.exchange_code(code="abc", code_verifier="verifier")
        profile = await ggg.get_profile("token")
        assert profile["name"] == "ExileOne#1234"


def test_ggg_error_implies_reauth_on_invalid_grant() -> None:
    assert ggg_error_implies_reauth(GGGError(400, {"detail": "invalid_grant"}))
    assert ggg_error_implies_reauth(GGGError(400, "invalid_grant"))
    assert not ggg_error_implies_reauth(GGGError(400, "bad request"))
    assert not ggg_error_implies_reauth(GGGError(401, "nope"))
