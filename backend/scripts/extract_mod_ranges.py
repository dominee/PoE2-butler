#!/usr/bin/env python3
"""Extract T1 mod range data from poe.ninja character export samples.

Reads all *.json files in mock-ggg/samples/ and builds a mod_ranges.json
database by collecting extended mod data across all items.

Usage:
    uv run python backend/scripts/extract_mod_ranges.py

Output:
    backend/app/data/mod_ranges.json
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).parents[2]
SAMPLES_DIR = ROOT / "mock-ggg" / "samples"
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


def main() -> None:
    # stat_hash → { tier → {min, max, count} }
    db: dict[str, dict[int, dict]] = {}

    sample_files = list(SAMPLES_DIR.glob("*.json"))
    if not sample_files:
        print(f"No *.json files found in {SAMPLES_DIR}")
        return

    for path in sorted(sample_files):
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

    # Build output structure.
    output: dict = {"stat_hashes": {}}
    for stat_hash, tiers in sorted(db.items()):
        name = next(
            (v["name"] for v in tiers.values() if v.get("name")), ""
        )
        tier_list = sorted(
            [
                {
                    "tier": tier,
                    "min": round(v["min"], 4),
                    "max": round(v["max"], 4),
                    "count": v["count"],
                }
                for tier, v in tiers.items()
            ],
            key=lambda x: x["tier"],
        )
        output["stat_hashes"][stat_hash] = {
            "name": name,
            "tiers": tier_list,
        }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")

    total_hashes = len(output["stat_hashes"])
    t1_count = sum(
        1 for v in output["stat_hashes"].values() if any(t["tier"] == 1 for t in v["tiers"])
    )
    print(f"\nWrote {OUTPUT}")
    print(f"  {total_hashes} stat hashes, {t1_count} with T1 data")


if __name__ == "__main__":
    main()
