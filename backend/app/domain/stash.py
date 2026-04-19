"""Stash tab domain model."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.domain.item import Item, parse_item


class StashColour(BaseModel):
    r: int = 0
    g: int = 0
    b: int = 0


class StashTabSummary(BaseModel):
    id: str
    name: str
    type: str = "NormalStash"
    index: int = 0
    colour: StashColour | None = None


class StashTab(BaseModel):
    tab: StashTabSummary
    items: list[Item] = Field(default_factory=list)


def parse_tab_list(payload: dict[str, Any]) -> list[StashTabSummary]:
    raw = payload.get("tabs") or []
    out: list[StashTabSummary] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        colour = entry.get("colour") or entry.get("color")
        colour_model = None
        if isinstance(colour, dict):
            colour_model = StashColour(
                r=int(colour.get("r", 0)),
                g=int(colour.get("g", 0)),
                b=int(colour.get("b", 0)),
            )
        out.append(
            StashTabSummary(
                id=str(entry.get("id") or entry.get("name") or ""),
                name=str(entry.get("name", "")),
                type=str(entry.get("type", "NormalStash")),
                index=int(entry.get("index", 0)),
                colour=colour_model,
            )
        )
    return out


def parse_tab(tab_summary: StashTabSummary, payload: dict[str, Any]) -> StashTab:
    raw_items = payload.get("items") or []
    items = [parse_item(i) for i in raw_items if isinstance(i, dict)]
    return StashTab(tab=tab_summary, items=items)
