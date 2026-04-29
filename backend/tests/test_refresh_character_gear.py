"""Manual refresh should repopulate character gear snapshots (no pricing queue)."""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_refresh_calls_character_gear_prefetch(app_stack, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    async def track(*, league: str, **kwargs: object) -> None:
        calls.append(league)

    monkeypatch.setattr("app.api.refresh.refresh_character_gear_snapshots", track)

    _app, client, mock_app = app_stack
    from tests.test_auth_flow import _full_login

    await _full_login(client, mock_app)
    csrf = client.cookies.get("poe2b_csrf")
    assert csrf
    resp = await client.post("/api/refresh", headers={"X-CSRF-Token": csrf})
    assert resp.status_code == 200, resp.text
    assert len(calls) == 1
    assert calls[0]
