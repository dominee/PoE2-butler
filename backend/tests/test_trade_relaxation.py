"""Relaxation index ordering for trade stat filters."""

from __future__ import annotations

from app.services.trade_relaxation import apply_relaxation_step, stat_filter_drop_indices


def test_drop_order_crafted_before_explicit() -> None:
    filters = [
        {"bucket": "explicit", "id": "a"},
        {"bucket": "crafted", "id": "b"},
        {"bucket": "explicit", "id": "c"},
    ]
    order = stat_filter_drop_indices(filters)
    # crafted index 1 removed first → last in group is only b
    assert order[0] == 1
    # explicits: indices 2 then 0 (later first)
    assert order[1] == 2
    assert order[2] == 0


def test_apply_step_zero_is_full() -> None:
    f = [{"bucket": "explicit"}, {"bucket": "crafted"}]
    o = stat_filter_drop_indices(f)
    assert apply_relaxation_step(f, 0, o) == f
    one = apply_relaxation_step(f, 1, o)
    assert len(one) == 1
