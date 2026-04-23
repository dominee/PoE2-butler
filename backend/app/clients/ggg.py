"""Thin async client for the GGG OAuth2 + account API.

Rate-limit aware: parses ``X-Rate-Limit-*`` headers on every response and honours
``Retry-After`` on 429.  Caller is expected to back off further at the
application layer via the token bucket in :mod:`app.services.rate_limit`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

import httpx

from app.config import Settings
from app.logging import get_logger

log = get_logger("app.clients.ggg")


class GGGError(Exception):
    """Raised when GGG returns a non-success response we cannot recover from."""

    def __init__(self, status_code: int, payload: Any) -> None:
        super().__init__(f"GGG {status_code}: {payload!r}")
        self.status_code = status_code
        self.payload = payload


@dataclass
class TokenResponse:
    access_token: str
    refresh_token: str | None
    expires_in: int
    scope: str


class GGGClient:
    def __init__(self, settings: Settings, *, client: httpx.AsyncClient | None = None) -> None:
        self._settings = settings
        self._client = client or httpx.AsyncClient(timeout=httpx.Timeout(15.0))
        self._user_agent = (
            f"OAuth {settings.ggg_client_id}/{settings.app_version} "
            f"(contact: {settings.ggg_user_agent_contact}) "
            f"{settings.ggg_user_agent_suffix}"
        ).strip()

    async def aclose(self) -> None:
        await self._client.aclose()

    def authorize_url(self, *, state: str, code_challenge: str) -> str:
        # Use the browser-facing base URL if explicitly configured (needed in
        # dev where the IdP internal hostname is unreachable from the browser).
        base = (
            self._settings.ggg_oauth_authorize_base_url
            or self._settings.ggg_oauth_base_url
        )
        params = {
            "client_id": self._settings.ggg_client_id,
            "response_type": "code",
            "scope": self._settings.ggg_scopes,
            "state": state,
            "redirect_uri": self._settings.ggg_redirect_uri,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
        return f"{base}/oauth/authorize?{urlencode(params)}"

    async def exchange_code(self, *, code: str, code_verifier: str) -> TokenResponse:
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self._settings.ggg_redirect_uri,
            "code_verifier": code_verifier,
            "client_id": self._settings.ggg_client_id,
            "client_secret": self._settings.ggg_client_secret.get_secret_value(),
        }
        return await self._post_token(data)

    async def refresh_token(self, refresh_token: str) -> TokenResponse:
        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": self._settings.ggg_client_id,
            "client_secret": self._settings.ggg_client_secret.get_secret_value(),
        }
        return await self._post_token(data)

    async def revoke(self, token: str) -> None:
        url = f"{self._settings.ggg_oauth_base_url}/oauth/revoke"
        try:
            await self._client.post(
                url,
                data={"token": token},
                headers={"User-Agent": self._user_agent},
            )
        except httpx.HTTPError as exc:  # best-effort
            log.warning("ggg.revoke_failed", error=str(exc))

    async def _post_token(self, data: dict[str, str]) -> TokenResponse:
        url = f"{self._settings.ggg_oauth_base_url}/oauth/token"
        resp = await self._client.post(url, data=data, headers={"User-Agent": self._user_agent})
        self._record_rate_limit(resp)
        if resp.status_code >= 400:
            raise GGGError(resp.status_code, self._safe_body(resp))
        body = resp.json()
        return TokenResponse(
            access_token=body["access_token"],
            refresh_token=body.get("refresh_token"),
            expires_in=int(body.get("expires_in", 0)),
            scope=body.get("scope", ""),
        )

    async def get_profile(self, access_token: str) -> dict[str, Any]:
        return await self._get("/profile", access_token)

    async def get_leagues(self, access_token: str) -> dict[str, Any]:
        return await self._get("/account/leagues", access_token)

    async def get_characters(self, access_token: str) -> dict[str, Any]:
        return await self._get("/account/characters", access_token)

    async def get_character(self, access_token: str, name: str) -> dict[str, Any]:
        return await self._get(f"/account/characters/{name}", access_token)

    async def get_stash_list(self, access_token: str, league: str) -> dict[str, Any]:
        return await self._get(f"/account/stashes/{league}", access_token)

    async def get_stash_tab(
        self, access_token: str, league: str, tab_id: str
    ) -> dict[str, Any]:
        return await self._get(f"/account/stashes/{league}/{tab_id}", access_token)

    async def _get(self, path: str, access_token: str) -> dict[str, Any]:
        url = f"{self._settings.ggg_api_base_url}{path}"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "User-Agent": self._user_agent,
        }
        resp = await self._client.get(url, headers=headers)
        self._record_rate_limit(resp)
        if resp.status_code >= 400:
            raise GGGError(resp.status_code, self._safe_body(resp))
        return resp.json()

    @staticmethod
    def _record_rate_limit(resp: httpx.Response) -> None:
        rl = {k: v for k, v in resp.headers.items() if k.lower().startswith("x-rate-limit-")}
        if rl:
            log.debug("ggg.rate_limit", **rl)

    @staticmethod
    def _safe_body(resp: httpx.Response) -> Any:
        ct = resp.headers.get("content-type", "")
        if "json" in ct:
            try:
                return resp.json()
            except ValueError:
                return resp.text[:500]
        return resp.text[:500]
