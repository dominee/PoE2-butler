#!/usr/bin/env python3
"""Populate ``stat_hashes`` in mod_ranges.json from poe.ninja character export samples.

Reads all *.json files in the samples directory (default: mock-ggg/samples/)
and collects observed (hash, name, tier, min, max) tuples from
``extended.mods``.

For each observed stat hash, the script first attempts to resolve the mod's
display name against the ``mod_names`` section written by
``ingest_repoe_mods.py``.  When a match is found the **authoritative** RePoE
ranges are used instead of the widest-observed approach, giving accurate
T1 min/max values.

Run **after** ``ingest_repoe_mods.py`` to benefit from RePoE enrichment:
    uv run python backend/scripts/ingest_repoe_mods.py
    uv run python backend/scripts/extract_mod_ranges.py

Pass extra sample directories to broaden hash coverage beyond the bundled set:
    uv run python backend/scripts/extract_mod_ranges.py \\
        --samples mock-ggg/samples /path/to/more/samples

Use ``--limited N`` for a quick smoke-test against only the first N files:
    uv run python backend/scripts/extract_mod_ranges.py --limited 3

Output:
    backend/app/data/mod_ranges.json  (stat_hashes section updated)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parents[2]
_DEFAULT_SAMPLES_DIR = ROOT / "mock-ggg" / "samples"
OUTPUT = ROOT / "backend" / "app" / "data" / "mod_ranges.json"

# Tier string → numeric tier (e.g. "S1" → 1, "P3" → 3, "1" → 1)
_TIER_RE = re.compile(r"\d+")


def parse_tier(tier_raw: object) -> int | None:
    if tier_raw is None:
        return None
    try:
        return int(tier_raw)
    except (TypeError, ValueError):
        m = _TIER_RE.search(str(tier_raw))
        return int(m.group()) if m else None


def iter_items(data: dict) -> list[dict]:
    """Recursively yield all item dicts from a poe.ninja export."""
    items: list[dict] = []
    char_model = data.get("charModel") or {}
    for item in char_model.get("items", []):
        if isinstance(item, dict):
            items.append(item)
            for si in item.get("socketedItems", []):
                if isinstance(si, dict):
                    items.append(si)
    for jewel in char_model.get("jewels", []):
        if isinstance(jewel, dict):
            items.append(jewel)
    return items


def _load_existing() -> dict:
    """Return the current mod_ranges.json (empty dict if absent/unreadable)."""
    if not OUTPUT.exists():
        return {}
    try:
        return json.loads(OUTPUT.read_text(encoding="utf-8"))
    except Exception:
        return {}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--samples",
        metavar="DIR",
        nargs="+",
        default=[str(_DEFAULT_SAMPLES_DIR)],
        help=(
            "One or more directories containing poe.ninja *.json character "
            f"exports (default: {_DEFAULT_SAMPLES_DIR}). "
            "Pass extra paths to broaden stat_hash coverage."
        ),
    )
    parser.add_argument(
        "--limited",
        metavar="N",
        type=int,
        default=None,
        help=(
            "Process only the first N sample files across all directories. "
            "Useful for a quick smoke-test."
        ),
    )
    args = parser.parse_args(argv)

    # Collect all sample files from the requested directories.
    all_sample_files: list[Path] = []
    for raw_dir in args.samples:
        d = Path(raw_dir)
        if not d.is_dir():
            print(f"Warning: samples directory not found, skipping: {d}", file=sys.stderr)
            continue
        all_sample_files.extend(sorted(d.glob("*.json")))

    if not all_sample_files:
        print("No *.json sample files found in the specified directories.", file=sys.stderr)
        return 1

    if args.limited is not None:
        all_sample_files = all_sample_files[: args.limited]
        print(f"--limited {args.limited}: using {len(all_sample_files)} file(s)")

    print(f"Sample files to process: {len(all_sample_files)}")

    # stat_hash → { tier → {min, max, count, name} }
    db: dict[str, dict[int, dict]] = {}

    # Load existing mod_ranges.json to access mod_names for RePoE enrichment.
    existing = _load_existing()
    repoe_mod_names: dict[str, dict] = existing.get("mod_names") or {}
    repoe_enriched = 0

    for path in all_sample_files:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            print(f"  skip {path.name}: {exc}")
            continue

        items = iter_items(data)
        print(f"  {path.name}: {len(items)} items")

        for item in items:
            extended = item.get("extended")
            if not isinstance(extended, dict):
                continue
            mods = extended.get("mods")
            if not isinstance(mods, dict):
                continue

            for mod_entry in mods.get("explicit") or []:
                if not isinstance(mod_entry, dict):
                    continue
                tier = parse_tier(mod_entry.get("tier"))
                if tier is None:
                    continue

                for mag in mod_entry.get("magnitudes") or []:
                    if not isinstance(mag, dict):
                        continue
                    stat_hash = str(mag.get("hash", "")).strip()
                    if not stat_hash:
                        continue
                    mag_min = mag.get("min")
                    mag_max = mag.get("max")
                    if mag_min is None or mag_max is None:
                        continue

                    if stat_hash not in db:
                        db[stat_hash] = {}
                    if tier not in db[stat_hash]:
                        db[stat_hash][tier] = {
                            "min": float(mag_min),
                            "max": float(mag_max),
                            "count": 1,
                            "name": str(mod_entry.get("name", "")),
                        }
                    else:
                        entry = db[stat_hash][tier]
                        # Keep the widest observed range.
                        entry["min"] = min(entry["min"], float(mag_min))
                        entry["max"] = max(entry["max"], float(mag_max))
                        entry["count"] += 1

    # Build output structure, enriching with RePoE authoritative ranges where possible.
    stat_hashes: dict = {}
    for stat_hash, tiers in sorted(db.items()):
        mod_name = next(
            (v["name"] for v in tiers.values() if v.get("name")), ""
        )
        repoe_entry = repoe_mod_names.get(mod_name) if mod_name else None
        tier_list = []
        for tier, v in sorted(tiers.items(), key=lambda x: x[0]):
            tier_entry: dict = {
                "tier": tier,
                "min": round(v["min"], 4),
                "max": round(v["max"], 4),
                "count": v["count"],
            }
            if repoe_entry:
                # Find the matching RePoE tier by tier_ggg number.
                repoe_stats = repoe_entry.get("stats") or []
                primary_stat = repoe_stats[0] if repoe_stats else {}
                # Look up authoritative range from the RePoE group.
                repoe_groups: dict = existing.get("mod_groups") or {}
                group_tiers = repoe_groups.get(repoe_entry.get("group", "")) or []
                repoe_tier = next(
                    (t for t in group_tiers if t.get("tier_ggg") == tier), None
                )
                if repoe_tier:
                    stats = repoe_tier.get("stats") or []
                    primary = stats[0] if stats else {}
                    if primary.get("min") is not None and primary.get("max") is not None:
                        tier_entry["min"] = float(primary["min"])
                        tier_entry["max"] = float(primary["max"])
                        tier_entry["repoe"] = True
                        repoe_enriched += 1
                elif primary_stat and tier == repoe_entry.get("tier_ggg"):
                    if primary_stat.get("min") is not None and primary_stat.get("max") is not None:
                        tier_entry["min"] = float(primary_stat["min"])
                        tier_entry["max"] = float(primary_stat["max"])
                        tier_entry["repoe"] = True
                        repoe_enriched += 1
            tier_list.append(tier_entry)
        stat_hashes[stat_hash] = {
            "name": mod_name,
            "tiers": tier_list,
        }

    # Preserve mod_names and mod_groups from the existing file.
    output: dict = {
        "stat_hashes": stat_hashes,
        "mod_names": existing.get("mod_names") or {},
        "mod_groups": existing.get("mod_groups") or {},
    }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")

    total_hashes = len(output["stat_hashes"])
    t1_count = sum(
        1 for v in output["stat_hashes"].values() if any(t["tier"] == 1 for t in v["tiers"])
    )
    print(f"\nWrote {OUTPUT}")
    print(f"  {total_hashes} stat hashes, {t1_count} with T1 data")
    if repoe_mod_names:
        print(f"  {repoe_enriched} tier ranges replaced with authoritative RePoE data")
    else:
        print("  (no mod_names in DB — run ingest_repoe_mods.py first for enrichment)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
