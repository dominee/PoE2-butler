"""League domain model."""

from __future__ import annotations

from pydantic import BaseModel


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
