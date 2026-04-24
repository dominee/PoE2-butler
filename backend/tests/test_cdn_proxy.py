"""Allowlisted PoE CDN image proxy (canvas-safe for the SPA)."""

from __future__ import annotations

import pytest
from httpx import Response
from tests.test_auth_flow import _full_login

OK_URL = (
    "https://web.poecdn.com/gen/image/WzI1LDE0LHsiZiI6IngiLCJ3IjoxLCJoIjoxfV0/1/x.png"
)


@pytest.mark.asyncio
async def test_poecdn_requires_session(app_stack) -> None:  # type: ignore[no-untyped-def]
    _app, client, _mock = app_stack
    r = await client.get("/api/cdn/poecdn", params={"u": OK_URL})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_poecdn_rejects_non_allowlisted_host(app_stack) -> None:  # type: ignore[no-untyped-def]
    _app, client, mock_app = app_stack
    await _full_login(client, mock_app)
    r = await client.get(
        "/api/cdn/poecdn",
        params={"u": "https://malicious.example.com/steal.png"},
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_poecdn_proxies_png(app_stack, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    _app, client, mock_app = app_stack
    await _full_login(client, mock_app)

    class _FakeClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return None

        async def get(self, url, headers=None):
            assert "web.poecdn.com" in url
            return Response(200, content=b"\x89PNG\r\n", headers={"content-type": "image/png"})

    monkeypatch.setattr("app.api.cdn_proxy.httpx.AsyncClient", _FakeClient)

    r = await client.get("/api/cdn/poecdn", params={"u": OK_URL})
    assert r.status_code == 200
    assert r.content.startswith(b"\x89PNG")
    assert "image" in (r.headers.get("content-type") or "")
