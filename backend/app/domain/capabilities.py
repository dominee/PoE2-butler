"""Server-reported feature flags derived from granted GGG OAuth scopes."""

from __future__ import annotations

from pydantic import BaseModel

from app.config import Settings


class Capabilities(BaseModel):
    """What the current deployment can offer (scope-driven, not per-user)."""

    stash_available: bool
    leagues_inferred: bool


def capabilities_from_settings(settings: Settings) -> Capabilities:
    return Capabilities(
        stash_available=settings.stash_oauth_available,
        leagues_inferred=not settings.leagues_oauth_available,
    )
