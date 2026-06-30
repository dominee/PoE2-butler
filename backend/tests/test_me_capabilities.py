"""Tests for GET /api/me capabilities flags."""

from __future__ import annotations

import pytest

from app.domain.capabilities import capabilities_from_settings


def test_capabilities_prod_scopes() -> None:
    from app.config import Settings

    settings = Settings(
        ggg_scopes="account:profile account:characters",
        _env_file=None,
    )
    caps = capabilities_from_settings(settings)
    assert caps.stash_available is False
    assert caps.leagues_inferred is True


def test_capabilities_dev_mock_scopes() -> None:
    from app.config import Settings

    settings = Settings(
        ggg_scopes="account:profile account:characters account:stashes account:leagues",
        _env_file=None,
    )
    caps = capabilities_from_settings(settings)
    assert caps.stash_available is True
    assert caps.leagues_inferred is False
