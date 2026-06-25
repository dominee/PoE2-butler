"""League domain model."""

from __future__ import annotations

from collections import Counter
from typing import TYPE_CHECKING

from pydantic import BaseModel

if TYPE_CHECKING:
    from app.domain.character import CharacterSummary


class League(BaseModel):
    id: str
    realm: str = "pc"
    description: str | None = None
    current: bool = False


def parse_leagues(payload: dict) -> list[League]:
    """Normalize the GGG ``/account/leagues`` payload into a list of :class:`League`."""
    raw = payload.get("leagues") or payload.get("items") or []
    out: list[League] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        lid = entry.get("id") or entry.get("name")
        if not lid:
            continue
        out.append(
            League(
                id=str(lid),
                realm=str(entry.get("realm", "pc")),
                description=entry.get("description"),
                current=bool(entry.get("current", False)),
            )
        )
    return out


def pick_current_league(leagues: list[League]) -> str | None:
    for league in leagues:
        if league.current and not league.id.lower().startswith("hardcore"):
            return league.id
    for league in leagues:
        if league.current:
            return league.id
    return leagues[0].id if leagues else None


def resolve_leagues_current(leagues: list[League], preferred: str | None) -> str | None:
    """Pick the league id exposed as ``current`` in GET /api/leagues.

    When at least one league carries ``current=True`` (GGG snapshot or synthesized
    from ``preferred``), use :func:`pick_current_league`. Otherwise fall back to
    ``preferred``, then the first league in the list.
    """
    if any(lg.current for lg in leagues):
        return pick_current_league(leagues)
    if preferred:
        return preferred
    return pick_current_league(leagues)


# Permanent leagues never expire; a character in one of these is not a signal
# that the player is actively playing a challenge league.
_PERMANENT_LEAGUES = frozenset(
    {"standard", "hardcore", "ssf standard", "ssf hardcore", "hardcore ssf"}
)


def pick_league_from_characters(summaries: list[CharacterSummary]) -> str | None:
    """Infer the preferred league from character summaries.

    Used when ``account:leagues`` scope is unavailable (e.g. not granted by GGG).
    Prefers the most common non-permanent (challenge) league; falls back to the
    first league present in the character list if all are permanent.
    """
    leagues: list[str] = [c.league for c in summaries if c.league]
    if not leagues:
        return None
    non_perm = [lg for lg in leagues if lg.lower() not in _PERMANENT_LEAGUES]
    candidates = non_perm if non_perm else leagues
    return Counter(candidates).most_common(1)[0][0]
