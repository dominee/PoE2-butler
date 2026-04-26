"""Poe.ninja events API: SSE vs JSON version resolution."""

from __future__ import annotations

import httpx
import pytest

from app.ninja_urls import NinjaCharacterRef
from app.poe_ninja import fetch_events_version


def test_fetch_events_version_from_sse_first_data_line(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MOCK_GGG_POE_NINJA_MIN_INTERVAL_SEC", "0")

    def transport(request: httpx.Request) -> httpx.Response:
        assert "/poe2/api/events/character/" in str(request.url)
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream; charset=utf-8"},
            text='data: {"version": 424242}\n\n',
        )

    ref = NinjaCharacterRef("TestAcct-0000", "vaal", "TestChar")
    with httpx.Client(transport=httpx.MockTransport(transport)) as client:
        assert fetch_events_version(client, ref) == 424242


def test_fetch_events_version_from_json_body(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MOCK_GGG_POE_NINJA_MIN_INTERVAL_SEC", "0")

    def transport(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-type": "application/json"},
            json={"data": {"version": 7}},
        )

    ref = NinjaCharacterRef("a", "vaal", "b")
    with httpx.Client(transport=httpx.MockTransport(transport)) as client:
        assert fetch_events_version(client, ref) == 7
