"""Security middleware tests."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from admin.app.main import app


@pytest.mark.asyncio
async def test_csp_allows_chartjs_cdn() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/admin/login")
    assert resp.status_code == 200
    csp = resp.headers.get("content-security-policy", "")
    assert "script-src" in csp
    assert "cdn.jsdelivr.net" in csp
