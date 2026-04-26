"""Bundled Poe.ninja TOML must stay valid so dev login lists ninja-backed OAuth users."""

from __future__ import annotations

from app.ninja_config import default_toml_path, load_character_refs


def test_bundled_poe_ninja_characters_toml_parses() -> None:
    path = default_toml_path()
    assert path.is_file(), f"missing bundled TOML: {path}"
    refs = load_character_refs(path)
    assert len(refs) >= 2, "expected multiple character URLs from bundled config"
