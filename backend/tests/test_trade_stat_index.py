"""Tests for PoE2 trade stat id index + payload enrichment."""

from __future__ import annotations

import pytest

import app.services.trade_stat_index as tsi


@pytest.fixture(autouse=True)
def _reset_trade_stat_index() -> None:
    tsi.reset_trade_stats_index_for_tests()
    yield
    tsi.reset_trade_stats_index_for_tests()


def test_enrich_fills_id_from_loaded_index() -> None:
    tsi.reset_trade_stats_index_for_tests()
    tsi._stats_ready = True
    tsi._by_prefix_norm = {
        ("explicit", "# to maximum Mana"): "explicit.stat_1050105434",
    }
    payload = {
        "query": {
            "stats": [
                {
                    "type": "and",
                    "filters": [
                        {
                            "bucket": "explicit",
                            "text": "+50 to maximum Mana",
                            "template": "# to maximum Mana",
                            "value": {"min": 40, "max": 60},
                        }
                    ],
                }
            ],
        },
    }
    tsi.enrich_trade_payload_stat_ids(payload)
    assert payload["query"]["stats"][0]["filters"][0]["id"] == "explicit.stat_1050105434"


def test_lookup_falls_back_to_bundled_when_index_misses() -> None:
    tsi.reset_trade_stats_index_for_tests()
    tsi._stats_ready = True
    tsi._by_prefix_norm = {}
    assert tsi.lookup_trade_stat_id("explicit", "# to maximum Life") == "explicit.stat_3299347043"


def test_lookup_implicit_prefix() -> None:
    tsi.reset_trade_stats_index_for_tests()
    tsi._stats_ready = True
    tsi._by_prefix_norm = {
        ("implicit", "# to Spirit"): "implicit.stat_3981240776",
    }
    assert tsi.lookup_trade_stat_id("implicit", "# to Spirit") == "implicit.stat_3981240776"
