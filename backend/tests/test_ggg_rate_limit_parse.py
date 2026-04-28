"""Parse GGG trade2 429 JSON bodies."""

from app.services.third_party_ratelimit import parse_ggg_rate_limit_wait_sec


def test_parse_wait_seconds() -> None:
    body = (
        '{"error":{"code":3,"message":'
        '"Rate limit exceeded; Please wait 291 seconds before trying again."}}'
    )
    assert parse_ggg_rate_limit_wait_sec(body) == 291


def test_parse_wait_missing() -> None:
    assert parse_ggg_rate_limit_wait_sec("{}") is None
