"""Parse poe.ninja character page URLs into API path segments."""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlparse

_PROFILE_RE = re.compile(
    r"^/poe2/profile/(?P<account>[^/]+)/(?P<league>[^/]+)/character/(?P<name>[^/]+)/?$",
    re.IGNORECASE,
)
_BUILDS_RE = re.compile(
    r"^/poe2/builds/(?P<league>[^/]+)/character/(?P<account>[^/]+)/(?P<name>[^/]+)/?$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class NinjaCharacterRef:
    """Segments used in poe.ninja API paths."""

    account: str
    league_slug: str
    character_name: str


def parse_character_url(url: str) -> NinjaCharacterRef:
    raw = (url or "").strip()
    if not raw:
        raise ValueError("empty_url")
    parsed = urlparse(raw)
    path = parsed.path or ""
    path = path.rstrip("/") or "/"
    m = _PROFILE_RE.match(path)
    if m:
        return NinjaCharacterRef(
            account=m.group("account"),
            league_slug=m.group("league"),
            character_name=m.group("name"),
        )
    m = _BUILDS_RE.match(path)
    if m:
        return NinjaCharacterRef(
            account=m.group("account"),
            league_slug=m.group("league"),
            character_name=m.group("name"),
        )
    raise ValueError(f"unsupported_poe_ninja_character_url:{raw}")
