# Unique item reference (flavour + community roll templates)

## Purpose

Some GGG item payloads **omit `flavourText`**, and **per-mod `extended.magnitudes` describe this instance’s roll**, not the **base unique’s** possible range (the numbers players expect from community databases).

The app ships **`backend/app/data/unique_reference.json`**: a small, bundled list of uniques (matched by `name` + `baseType`) with:

- **`flavour`**: the unique quote, used when the snapshot has no GGG flavour.
- **`mod_range_hints`**: a list of `{ "when_contains", "range" }` strings used only for **in-app display** of wiki-style “type” roll ranges (right column next to each mod line on uniques; see the item detail pane). This is **not** GGG snapshot data.

Matching is **substring, longest `when_contains` wins**, after the same GGG **tag-stripping** as the main item parser (see `backend/app/domain/item.py` and `_reference_range_for_mod_line`).

## Data shape

`unique_reference.json` is a top-level object:

```json
{
  "entries": [
    {
      "name": "My Unique",
      "base_type": "Heavy Belt",
      "flavour": "Optional. Multi-line string.",
      "mod_range_hints": [
        { "when_contains": "maximum life", "range": "+(40—60)" },
        { "when_contains": "charm", "range": "(1—3) Slots" }
      ]
    }
  ]
}
```

- **`name` / `base_type`**: must match the normalized `Item` after `parse_item` (GGG `name` and `baseType` / `typeLine` as in code).
- **`flavour`**: applied only if the parsed item has no flavour from GGG.
- **`mod_range_hints`**: `when_contains` is matched **case-insensitively** against the **tag-stripped** mod line. Keep phrases **specific** enough to hit the right line on that unique; the resolver prefers a **longer** `when_contains` over a shorter one when both match.

## Regenerating from poe2db.tw

**Source:** [poe2db.tw](https://poe2db.tw) (CC BY-NC-SA 3.0). The ingest script fetches public pages, extracts the embedded GGG JSON for flavour, and reads roll lines from the **`implicitMod` / `explicitMod`** (and similar) `div` text. It is a **maintainer** tool; **review the JSON** before committing (patches, new leagues, and HTML changes can make lines noisy or empty).

**Run** (from `backend/`), writing the data file the app loads:

```bash
cd backend
uv run python scripts/ingest_poe2db_uniques.py --from-mock --out app/data/unique_reference.json
```

- **`--from-mock`**: collect unique `name` + `baseType` from `mock-ggg/app/fixtures/*.json` (all uniques referenced in those fixtures).
- **Optional** `Name|BaseType` arguments instead of `--from-mock` for a subset.
- **Throttle**: default ~0.55s between HTTP requests. Use a **clear User-Agent** and **do not** hammer the site.

**Wiki URL slug:** unique name with apostrophes removed, spaces to underscores (e.g. `Maligaro's Virtuosity` → `Maligaros_Virtuosity`).

**Limitations of automated ingest**

- Some uniques (e.g. certain **jewels** or **fixed** mods) may have **flavour but no `N—M` lines** in those mod `div`s; the script leaves **`mod_range_hints` absent** for that entry. Hand-edit the JSON for one-off cases if needed.
- Lines containing internal or **hidden** stat phrasing, **dual** damage ranges, or “Grants skill” boilerplate are **filtered out** to avoid bad `when_contains` keys.

## Legal / product note

- **poe2db** content is community wiki material under its own license; this repo stores **processed** snippets for display only, not a mirror of the full site.
- This product is **not affiliated with** Grinding Gear Games. Roll templates in the JSON are **community / wiki style**, not official definitive rolls.

## Related code

| Piece | Path |
|-------|------|
| Data file | `backend/app/data/unique_reference.json` |
| Loader + lookup | `backend/app/services/unique_reference.py` |
| `parse_item` merge + per-mod columns | `backend/app/domain/item.py` (`implicit_mod_range_hints`, `explicit_mod_range_hints`) |
| Ingest script | `backend/scripts/ingest_poe2db_uniques.py` |
| UI (inline range column on uniques) | `frontend/src/features/items/ItemModPresentation.tsx` (`ExplicitModLine` / `referenceRangeText`) |
