"""Serialize :class:`Item` to PoE2-style item text (clipboard / export)."""

from __future__ import annotations

from app.domain.item import Item, ItemProperty, Socket, _strip_tags

SEP = "--------\n"


def _format_requirements_line(reqs: list[ItemProperty]) -> str:
    if not reqs:
        return ""
    level_first: str | None = None
    rest: list[str] = []
    for r in reqs:
        name = _strip_tags(r.name)
        val = (r.value or "").strip()
        if not val:
            continue
        if name.lower() == "level":
            level_first = f"Level {val}"
        elif name in ("Str", "Dex", "Int", "Str.", "Dex.", "Int."):
            clean = name.rstrip(".")
            rest.append(f"{val} {clean}")
        else:
            rest.append(f"{name} {val}")
    parts: list[str] = []
    if level_first:
        parts.append(level_first)
    parts.extend(rest)
    if not parts:
        return ""
    return "Requires: " + ", ".join(parts) + "\n"


def _socket_line(sockets: list[Socket]) -> str:
    if not sockets:
        return ""
    letters = " ".join("S" for _ in sockets)
    return f"Sockets: {letters} \n"


def _property_block(item: Item) -> str:
    if not item.properties:
        return ""
    lines: list[str] = []
    for p in item.properties:
        n = _strip_tags(p.name)
        if p.value is not None and p.value != "":
            lines.append(f"{n}: {p.value}")
        else:
            lines.append(n)
    return "\n".join(lines) + "\n"


def _mod_block(mods: list[str], *, tag: str | None = None) -> str:
    if not mods:
        return ""
    out: list[str] = []
    for m in mods:
        t = _strip_tags(m)
        if tag and not t.endswith(f"({tag})"):
            t = f"{t} ({tag})"
        out.append(t)
    return "\n".join(out) + "\n"


def format_item_text(item: Item) -> str:
    """Return a PoE2-style text block, similar to in-game copy (see ``mock-ggg/samples``)."""
    out_parts: list[str] = []
    h: list[str] = []
    if item.item_class:
        h.append(f"Item Class: {item.item_class}")
    h.append(f"Rarity: {item.rarity}")
    name = _strip_tags(item.name) if item.name else ""
    tline = _strip_tags(item.type_line) if item.type_line else ""
    if item.rarity == "Magic" and name and not tline:
        h.append(name)
    elif name and tline and name != tline:
        h.append(name)
        h.append(tline)
    elif name:
        h.append(name)
    elif tline:
        h.append(tline)
    out_parts.append("\n".join(h) + "\n")

    pb = _property_block(item)
    if pb:
        out_parts.append(SEP + pb)

    rline = _format_requirements_line(item.requirements)
    if rline:
        out_parts.append(SEP + rline)
    sk = _socket_line(item.sockets)
    if sk:
        out_parts.append(SEP + sk)
    if item.ilvl is not None:
        out_parts.append(SEP + f"Item Level: {item.ilvl}\n")

    if item.implicit_mods and _mod_block(item.implicit_mods, tag="implicit").strip():
        out_parts.append(SEP + _mod_block(item.implicit_mods, tag="implicit"))

    if item.rune_mods and _mod_block(item.rune_mods, tag="rune").strip():
        out_parts.append(SEP + _mod_block(item.rune_mods, tag="rune"))

    explicits: list[str] = []
    explicits.extend(item.explicit_mods)
    explicits.extend(item.crafted_mods)
    explicits.extend(item.enchant_mods)
    if explicits and _mod_block(explicits).strip():
        out_parts.append(SEP + _mod_block(explicits))

    if item.trailer_note and item.trailer_note.strip():
        out_parts.append(SEP + item.trailer_note.rstrip() + "\n")

    if item.flavour_text and item.flavour_text.strip():
        out_parts.append(SEP + item.flavour_text.rstrip() + "\n")

    if item.corrupted:
        out_parts.append(SEP + "Corrupted\n")

    return "".join(out_parts)
