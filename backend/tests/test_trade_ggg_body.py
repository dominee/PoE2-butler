"""Tests for GGG trade POST body normalization."""

from __future__ import annotations

from app.services.trade_ggg_body import ggg_search_body_from_result_payload


def test_ggg_body_strips_app_keys_and_stat_metadata() -> None:
    internal = {
        "query": {
            "status": {"option": "online"},
            "type": "Dualstring Bow",
            "filters": {"type_filters": {"filters": {"rarity": {"option": "rare"}}}},
            "stats": [
                {
                    "type": "and",
                    "filters": [
                        {
                            "bucket": "explicit",
                            "text": "+100 to maximum Life",
                            "template": "# to maximum Life",
                            "id": "explicit.stat_3299347043",
                            "value": {"min": 90, "max": 110},
                        }
                    ],
                }
            ],
            "mode": "exact",
            "tolerance_pct": 10,
        },
        "sort": {"price": "asc"},
        "mode": "exact",
        "tolerance_pct": 10,
    }
    body = ggg_search_body_from_result_payload(internal)
    assert body["sort"] == {"price": "asc"}
    q = body["query"]
    assert "mode" not in q
    assert "tolerance_pct" not in q
    f = q["stats"][0]["filters"][0]
    assert set(f.keys()) == {"id", "value"}
    assert f["id"] == "explicit.stat_3299347043"
    assert f["value"] == {"min": 90, "max": 110}


def test_ggg_body_drops_stat_filters_without_id() -> None:
    internal = {
        "query": {
            "status": {"option": "online"},
            "stats": [
                {
                    "type": "and",
                    "filters": [
                        {
                            "bucket": "explicit",
                            "text": "Some text mod",
                            "template": "No numbers here",
                        }
                    ],
                }
            ],
        },
        "sort": {"price": "asc"},
    }
    body = ggg_search_body_from_result_payload(internal)
    assert body["query"]["stats"][0]["filters"] == []
