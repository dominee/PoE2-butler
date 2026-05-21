"""Tests for PoE2 trade search POST (mocked transport)."""

from __future__ import annotations

from unittest.mock import patch

import httpx
import pytest

from app.config import Settings
from app.services.trade_search_submit import submit_trade_search, trade_search_post_url


def test_trade_search_post_url_encodes_league() -> None:
    s = Settings()
    assert trade_search_post_url(s, "Dawn of the Hunt") == (
        "https://www.pathofexile.com/api/trade2/search/Dawn%20of%20the%20Hunt"
    )


class _FakeClient:
    def __init__(self, *args: object, **kwargs: object) -> None:
        self.posted_url: str | None = None
        self.posted_json: dict | None = None

    async def __aenter__(self) -> _FakeClient:
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def post(
        self,
        url: str,
        *,
        json: dict | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        self.posted_url = url
        self.posted_json = json
        return httpx.Response(200, json={"id": "MockSearchId42", "result": [], "total": 0})


@pytest.mark.asyncio
async def test_submit_trade_search_returns_id() -> None:
    fake = _FakeClient()
    settings = Settings()
    payload = {
        "query": {
            "status": {"option": "securable"},
            "type": "Dualstring Bow",
            "filters": {},
        },
        "sort": {"price": "asc"},
    }
    with patch("app.services.trade_search_submit.httpx.AsyncClient", return_value=fake):
        sid, body, rate_limited, status_code = await submit_trade_search(
            settings, "Standard", payload
        )
    assert sid == "MockSearchId42"
    assert body is not None
    assert body.get("total") == 0
    assert rate_limited is False
    assert status_code == 200
    assert fake.posted_url is not None
    assert fake.posted_url.endswith("/Standard")
    assert fake.posted_json is not None
    assert fake.posted_json["query"]["status"]["option"] == "securable"


@pytest.mark.asyncio
async def test_submit_trade_search_empty_league_returns_none() -> None:
    settings = Settings()
    sid, body, rate_limited, status_code = await submit_trade_search(
        settings, "   ", {"query": {}, "sort": {}}
    )
    assert sid is None
    assert body is None
    assert rate_limited is False
    assert status_code == 0


@pytest.mark.asyncio
async def test_submit_trade_search_non_200_returns_none() -> None:
    class BadClient:
        async def __aenter__(self) -> BadClient:
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

        async def post(self, *args: object, **kwargs: object) -> httpx.Response:
            return httpx.Response(403, json={"error": "forbidden"})

    settings = Settings()
    with patch("app.services.trade_search_submit.httpx.AsyncClient", return_value=BadClient()):
        sid, body, rate_limited, status_code = await submit_trade_search(
            settings, "Standard", {"query": {}, "sort": {}}
        )
    assert sid is None
    assert body is None
    assert rate_limited is False
    assert status_code == 403
