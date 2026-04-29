"""GGG trade throttle helpers."""

from __future__ import annotations

from app.services.third_party_ratelimit import parse_retry_after_header


def test_parse_retry_after_header() -> None:
    assert parse_retry_after_header("60") == 60
    assert parse_retry_after_header("  120  ") == 120
    assert parse_retry_after_header(None) is None
    assert parse_retry_after_header("") is None
    assert parse_retry_after_header("not-a-number") is None
