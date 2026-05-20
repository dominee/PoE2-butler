#!/usr/bin/env python3
"""Ingest PoE2 mod tier data from the RePoE poe2 export.

Downloads ``https://repoe-fork.github.io/poe2/mods.min.json`` (or reads a
local copy with ``--input``) and writes two new sections into
``backend/app/data/mod_ranges.json``:

- ``mod_names``  — GGG mod display name → tier info.
  Bridge key: the ``name`` field in GGG's ``extended.mods`` entries matches
  the ``name`` field in RePoE exactly (e.g. ``"of the Volcano"``).

- ``mod_groups`` — mod family → all tiers, T1 first (highest required_level).
  Used to look up all available tiers for a mod and filter by item level.

Existing ``stat_hashes`` are preserved; only ``mod_names`` / ``mod_groups``
are regenerated.

By default ALL domains are ingested so that crafted (bench), sanctum, delve,
flask, and other player-visible prefixes/suffixes are included alongside
standard equipment mods.  Pass ``--limited`` to restrict to ``domain=item``
only, which is faster for a quick local smoke-test.

Run after each game patch (~quarterly):
    uv run python backend/scripts/ingest_repoe_mods.py
    uv run python backend/scripts/ingest_repoe_mods.py --input /path/to/mods.min.json
    uv run python backend/scripts/ingest_repoe_mods.py --limited   # item domain only

License note: RePoE data is derived from game files (© GGG); used for
non-commercial tool development per community convention.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).parents[2]
OUTPUT = ROOT / "backend" / "app" / "data" / "mod_ranges.json"
REPOE_URL = "https://repoe-fork.github.io/poe2/mods.min.json"

UA = "OAuth poe2-butler/1.0 (contact: dev@hell.sk) mod_tier_ingest; +https://hideoutbutler.com"

# Domains included in the full (default) run.  Covers all mod pools that can
# appear on player-equippable items: standard equipment, benchcrafted mods,
# abyss jewels, flasks, delve/fossil, sanctum relics, etc.
# Domains that never reach players (monster, strongbox, affliction, atlas …)
# are filtered out purely by their generation_type not being prefix/suffix, so
# explicitly listing them here is informational rather than load-bearing.
_ALL_PLAYER_DOMAINS = {
    "item",
    "crafted",
    "abyss_jewel",
    "flask",
    "delve",
    "sanctum",
}

# Domains used when --limited is passed (mirrors the original behaviour).
_LIMITED_DOMAINS = {"item"}

_ROLL_GEN_TYPES = {"prefix", "suffix"}


def fetch_repoe(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": UA})  # noqa: S310
    with urllib.request.urlopen(req, timeout=60) as r:  # noqa: S310
        return json.loads(r.read().decode("utf-8"))


def load_local(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def build_sections(
    mods: dict,
    domains: set[str] | None,
) -> tuple[dict, dict, dict]:
    """Return (mod_names, mod_groups, tag_index) built from a RePoE mods dict.

    Args:
        mods: Raw RePoE mods dict (from mods.min.json).
        domains: Allowlist of domain strings to include.  Pass ``None`` to
            accept every domain (equivalent to an infinite allowlist).

    RePoE keys mods as ``GroupName{n}`` (e.g. ``FireResist1``…``FireResist7``).
    Within each group:
      - Tiers are sorted by ``required_level`` ascending.
      - The last entry (highest required_level) is T1 (best / rarest).
      - Earlier entries are T2, T3 … Tn (n = total tier count).

    Both sections store **only the primary (first) stat** for brevity; callers
    needing multi-stat details can walk ``mod_groups`` fully.

    ``tag_index`` maps each GGG implicit_tag (e.g. ``"mana"``, ``"fire"``) to
    the sorted list of group names that carry that tag.  Used by the backend to
    infer which mod group a plain-text mod string belongs to when the item does
    not include GGG ``extended.mods`` data.
    """
    # group_name → list of raw RePoE entries
    groups: dict[str, list[dict]] = defaultdict(list)
    # group_name → set of implicit_tags across all entries in that group
    group_tags: dict[str, set[str]] = defaultdict(set)
    # domain → count of accepted entries (for summary stats)
    domain_counts: dict[str, int] = defaultdict(int)

    skipped_no_group = 0
    skipped_gen_type = 0
    skipped_domain = 0
    skipped_essence = 0

    for _mod_id, entry in mods.items():
        if not isinstance(entry, dict):
            continue
        domain = entry.get("domain") or ""
        if domains is not None and domain not in domains:
            skipped_domain += 1
            continue
        if entry.get("generation_type") not in _ROLL_GEN_TYPES:
            skipped_gen_type += 1
            continue
        if entry.get("is_essence_only"):
            skipped_essence += 1
            continue
        grp_list = entry.get("groups") or []
        if not grp_list:
            skipped_no_group += 1
            continue
        group = str(grp_list[0])
        groups[group].append(entry)
        domain_counts[domain] += 1
        for tag in entry.get("implicit_tags") or []:
            group_tags[group].add(str(tag))

    print(f"  Groups collected:      {len(groups)}")
    print(f"  Skipped (domain):      {skipped_domain}")
    print(f"  Skipped (gen_type):    {skipped_gen_type}")
    print(f"  Skipped (essence):     {skipped_essence}")
    print(f"  Skipped (no group):    {skipped_no_group}")
    if domain_counts:
        print("  Domain breakdown:")
        for dom, cnt in sorted(domain_counts.items(), key=lambda x: -x[1]):
            print(f"    {dom:<20} {cnt}")

    mod_names: dict[str, dict] = {}
    mod_groups: dict[str, list[dict]] = {}
    dup_names: list[str] = []

    for group, entries in sorted(groups.items()):
        # Sort by required_level ascending; last entry = T1.
        entries_sorted = sorted(entries, key=lambda e: e.get("required_level") or 0)
        total = len(entries_sorted)

        tier_list: list[dict] = []
        for idx, entry in enumerate(entries_sorted):
            tier_ggg = total - idx  # last entry → 1 (T1), first → total (Tn)
            stats_raw = entry.get("stats") or []
            # Build a compact stats list; keep all stats for completeness.
            stats: list[dict] = []
            for s in stats_raw:
                if not isinstance(s, dict):
                    continue
                stats.append(
                    {
                        "id": str(s.get("id", "")),
                        "min": s.get("min"),
                        "max": s.get("max"),
                    }
                )

            primary = stats[0] if stats else {}
            name = str(entry.get("name") or "").strip()
            req_level = entry.get("required_level") or 0

            tier_entry: dict = {
                "tier_ggg": tier_ggg,
                "required_level": req_level,
                "name": name,
                "stats": stats,
            }
            tier_list.append(tier_entry)

            # mod_names: name → first occurrence (within or across groups).
            # Within-group duplicates (same name, same group, different stat variant)
            # are normal in PoE2 and safely ignored — the first entry wins.
            if name:
                if name in mod_names:
                    existing_group = mod_names[name]["group"]
                    if existing_group != group:
                        # Only warn on true cross-group ambiguity.
                        dup_names.append(f"{name!r} (groups: {existing_group!r} vs {group!r})")
                else:
                    mod_names[name] = {
                        "group": group,
                        "tier_ggg": tier_ggg,
                        "required_level": req_level,
                        "stats": stats,
                        # Primary stat shortcut (matches pickMagnitude index 0 in frontend).
                        "stat_id": primary.get("id", ""),
                        "min": primary.get("min"),
                        "max": primary.get("max"),
                    }

        # mod_groups stores tiers T1-first (reverse of entries_sorted).
        mod_groups[group] = list(reversed(tier_list))

    if dup_names:
        print(f"  Duplicate names ({len(dup_names)}, first occurrence kept):")
        for d in dup_names[:10]:
            print(f"    {d}")
        if len(dup_names) > 10:
            print(f"    … and {len(dup_names) - 10} more")

    # Build tag_index: tag → sorted list of group names that carry it.
    tag_index: dict[str, list[str]] = defaultdict(list)
    for group, tags in sorted(group_tags.items()):
        for tag in tags:
            tag_index[tag].append(group)
    # Sort each list for deterministic output.
    tag_index_out: dict[str, list[str]] = {
        k: sorted(v) for k, v in sorted(tag_index.items())
    }
    print(f"  tag_index entries:  {len(tag_index_out)} tags")

    return mod_names, mod_groups, tag_index_out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--input",
        metavar="FILE",
        help="Path to a local mods.min.json (skips download)",
    )
    parser.add_argument(
        "--limited",
        action="store_true",
        help=(
            "Restrict ingestion to domain='item' only (the original subset). "
            "Useful for a quick smoke-test without touching crafted/sanctum/etc."
        ),
    )
    parser.add_argument(
        "--domains",
        metavar="DOMAIN",
        nargs="+",
        help=(
            "Explicit list of domains to include (e.g. --domains item crafted). "
            "Overrides --limited. Default: all player-relevant domains."
        ),
    )
    args = parser.parse_args(argv)

    # Resolve domain filter.
    if args.domains:
        domains: set[str] | None = set(args.domains)
        print(f"Domain filter (explicit): {sorted(domains)}")
    elif args.limited:
        domains = _LIMITED_DOMAINS
        print(f"Domain filter (--limited): {sorted(domains)}")
    else:
        domains = _ALL_PLAYER_DOMAINS
        print(f"Domain filter (full):      {sorted(domains)}")

    # Load source data.
    if args.input:
        src = Path(args.input)
        print(f"Reading local file: {src}")
        mods = load_local(src)
    else:
        print(f"Downloading: {REPOE_URL}")
        try:
            mods = fetch_repoe(REPOE_URL)
        except Exception as exc:
            print(f"Download failed: {exc}", file=sys.stderr)
            print("Tip: use --input to supply a local copy.", file=sys.stderr)
            return 1

    print(f"  Total mod entries: {len(mods)}")

    # Build new sections.
    mod_names, mod_groups, tag_index = build_sections(mods, domains)
    print(f"  mod_names entries:  {len(mod_names)}")
    print(f"  mod_groups entries: {len(mod_groups)}")

    # Load existing mod_ranges.json to preserve stat_hashes.
    existing: dict = {}
    if OUTPUT.exists():
        try:
            existing = json.loads(OUTPUT.read_text(encoding="utf-8"))
        except Exception as exc:
            print(f"Warning: could not read existing {OUTPUT}: {exc}", file=sys.stderr)

    output: dict = {
        "stat_hashes": existing.get("stat_hashes") or {},
        "mod_names": mod_names,
        "mod_groups": mod_groups,
        "tag_index": tag_index,
    }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
    size_kb = OUTPUT.stat().st_size / 1024
    print(f"\nWrote {OUTPUT}  ({size_kb:.1f} KB)")
    print(f"  stat_hashes: {len(output['stat_hashes'])} entries (preserved)")
    print(f"  mod_names:   {len(output['mod_names'])} entries")
    print(f"  mod_groups:  {len(output['mod_groups'])} entries")
    print(f"  tag_index:   {len(output['tag_index'])} tags")
    return 0


if __name__ == "__main__":
    sys.exit(main())
