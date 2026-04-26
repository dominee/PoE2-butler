"""Load Poe.ninja character URL list from TOML."""

from __future__ import annotations

import os
import tomllib
from pathlib import Path

from ninja_urls import NinjaCharacterRef, parse_character_url

_APP_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _APP_DIR.parent
_DEFAULT_TOML = _REPO_ROOT / "config" / "poe_ninja_characters.toml"


def default_toml_path() -> Path:
    override = (os.environ.get("MOCK_GGG_POE_NINJA_TOML") or "").strip()
    return Path(override) if override else _DEFAULT_TOML


def load_character_refs(path: Path | None = None) -> list[NinjaCharacterRef]:
    p = path or default_toml_path()
    if not p.is_file():
        return []
    data = tomllib.loads(p.read_text(encoding="utf-8"))
    urls = data.get("character_urls")
    if not isinstance(urls, list):
        return []
    out: list[NinjaCharacterRef] = []
    for u in urls:
        if not isinstance(u, str):
            continue
        out.append(parse_character_url(u))
    return out
