#!/usr/bin/env python3
"""Scrape poe2db.tw unique pages: flavour (embedded JSON) + mod_range_hints from template lines.

Full maintainer documentation: ``docs/unique_reference.md`` (regeneration, data shape, license).

Usage:
  cd backend && uv run python scripts/ingest_poe2db_uniques.py --from-mock \\
    --out app/data/unique_reference.json

Review the output. PoE2DB content: CC BY-NC-SA 3.0. Throttle: ~0.55s between pages.
User-Agent is identifiable (per project AGENTS / GGG habit).
"""

from __future__ import annotations

import argparse
import html as html_mod
import json
import re
import sys
import time
import urllib.parse
from pathlib import Path

import httpx

D = "\u2014"  # em dash as used on poe2db for item rolls

UA = "OAuth poe2-butler/1.0 (contact: dev@hell.sk) unique_reference ingest; +https://hideoutbutler.com"


def slug(name: str) -> str:
    return re.sub(r"[''`]", "", name or "").replace(" ", "_").strip() or "x"


def http_get(url: str) -> str:
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != "https" or parsed.netloc != "poe2db.tw":
        raise OSError(f"unsupported URL for scrape: {url}")
    with httpx.Client(timeout=50.0, follow_redirects=False, headers={"User-Agent": UA}) as client:
        resp = client.get(url)
        resp.raise_for_status()
        return resp.text


def extract_json(html: str) -> dict | None:
    p = html.find('"realm"')
    if p < 0:
        return None
    a = html.rfind("{", 0, p)
    depth = 0
    for b in range(a, len(html)):
        if html[b] == "{":
            depth += 1
        elif html[b] == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(html[a : b + 1])
                except json.JSONDecodeError:
                    return None
    return None


def norm(s: str) -> str:
    s = s.replace("–", D).replace("—", D)
    s = re.sub(r"\[([^\]|]+)\|([^\]]+)\]", r"\2", s)
    s = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", s)
    s = re.sub(r"\[([^\]]+)\]", r"\1", s)
    # poe2db HTML often injects spaces: ( 1 — 3 ) → (1—3)
    s = re.sub(
        r"\(\s*([+\-]?[\d.]+)\s*" + re.escape(D) + r"\s*([+\-]?[\d.]+)\s*\)",
        r"(\1" + D + r"\2)",
        s,
    )
    s = re.sub(
        r"\(\s*([+\-]?[\d.]+)\s+-\s+([+\-]?[\d.]+)\s*\)",
        r"(\1" + D + r"\2)",
        s,
    )
    return s.strip()


def to_hint(line: str) -> dict[str, str] | None:
    t = re.sub(r"^#+\s*", "", line.strip())
    t = norm(t)
    if D not in t and not re.search(
        r"[\(][\d.]+\s*" + re.escape(D) + r"[\d.]+\s*[\)]", t
    ):
        return None
    tl = t.lower()
    if "family" in tl and "domains" in tl and "|" in t:
        return None

    if t.lower().startswith("has ") and "charm" in t.lower() and "slot" in t.lower():
        a = re.search(r"\(([\d.]+)" + re.escape(D) + r"([\d.]+)\)", t, re.I)
        if a:
            return {
                "when_contains": "charm",
                "range": f"({a[1]}{D}{a[2]}) Slots",
            }
    a = re.match(
        r"^(\+?)(\((?:[\d.]+" + re.escape(D) + r"[\d.]+)\))(\s*%\s*)?(.+)$",
        t,
    )
    if a:
        pfx, core, pcts, w = a[1] or "", a[2], a[3] or "", a[4]
        pc = pcts and "%" in pcts
        rng = pfx + core + ("%" if pc else "")
        w = w.lower().strip()
        w = re.sub(r"[\n\r\t]+", " ", w)
        w = w.replace(" , ", ", ")
        w = re.sub(r"\s+", " ", w).strip(" .,;")
        if w and 1 < len(w) < 220:
            return {"when_contains": w, "range": rng}
    return None


def mod_lines_from_html(page: str) -> list[str]:
    out: list[str] = []
    for m in re.finditer(
        r'class="(implicitMod|explicitMod|craftedMod|enchantMod|secMod|property)"[^>]*>([\s\S]*?)</div>',
        page,
        re.IGNORECASE,
    ):
        inner = m.group(2)
        t = re.sub(
            r"<(br|/br)\b[^>]*/?>", " ", str(inner), flags=re.IGNORECASE
        )
        t = re.sub(r"<[^>]+>", " ", t)
        t = html_mod.unescape(t)
        t = re.sub(r"\s+", " ", t).strip()
        n = norm(t)
        low = n.lower()
        if not t or (D not in n and not re.search(
            r"\((?:[\d.]+" + re.escape(D) + r"[\d.]+)\)", n
        )):
            continue
        if re.match(
            r"^Belts$|^Rings$|^Gloves$|^Helmets?$|^Bows?$|^Rune Daggers?|^Jewels?$",
            t,
            re.I,
        ):
            continue
        if any(
            s in low
            for s in (
                "implicit hidden",
                "local weapon",
                "exposure art",
                "scalable value",
            )
        ):
            continue
        if len(n) > 200:
            continue
        if "adds (" in low and " to (" in low:  # dual min–max; skip for hint mapping
            continue
        if low.startswith("grants skill:"):
            continue
        if low.count("(") - low.count(")") > 0 or n.count("(") > 4:  # malformed / nested junk
            continue
        out.append(t)
    if not out:
        page = re.sub(
            r"<(script|style|noscript)\b[^>]*>.*?</\1>",
            "\n",
            page,
            flags=re.IGNORECASE | re.DOTALL,
        )
        t = re.sub(r"<br\s*/?>", "\n", page, flags=re.IGNORECASE)
        t = re.sub(r"</(p|tr|h[0-3])>", "\n", t, flags=re.IGNORECASE)
        t = re.sub(r"<[^>]+>", " ", t)
        plain = html_mod.unescape(t)
        for raw in plain.splitlines():
            s0 = norm(raw.strip())
            if D in s0 and re.search(
                r"\([0-9.]+" + re.escape(D) + r"[\d.]+", s0
            ) and 5 < len(s0) < 500:
                out.append(raw.strip())
    return out


def build_hints(page: str) -> list[dict[str, str]]:
    m: dict[str, dict[str, str]] = {}
    for line in mod_lines_from_html(page):
        h = to_hint(line)
        if h:
            w = h["when_contains"]
            m[w] = h
    return sorted(m.values(), key=lambda d: -len(d["when_contains"]))


def jflav(j: dict) -> str | None:
    ft = j.get("flavourText")
    if isinstance(ft, list):
        return "\n".join(str(x) for x in ft).replace("\r", "").strip() or None
    if isinstance(ft, str) and ft.strip():
        return ft.strip()
    return None


def mock_pairs() -> list[tuple[str, str]]:
    root = Path(__file__).resolve().parents[2] / "mock-ggg" / "app" / "fixtures"
    seen: set[tuple[str, str]] = set()

    def visit(o: object) -> None:
        if isinstance(o, dict):
            if (str(o.get("rarity", "")).lower() == "unique") or o.get("frameType") == 3:
                n, bt = o.get("name") or "", o.get("baseType") or o.get("typeLine") or ""
                if n and str(n).strip():
                    seen.add((str(n).strip(), str(bt or "").strip()))
            for v in o.values():
                visit(v)
        elif isinstance(o, list):
            for it in o:
                visit(it)

    for f in root.glob("*.json"):
        visit(json.loads(f.read_text(encoding="utf-8")))
    return sorted(seen, key=lambda x: (x[0].lower(), x[1]))


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("pair", nargs="*", help="Name|BaseType; default: --from-mock")
    p.add_argument("--from-mock", action="store_true")
    p.add_argument("--delay", type=float, default=0.55)
    p.add_argument(
        "--out",
        type=Path,
        help="Write unique_reference JSON to this file (e.g. app/data/unique_reference.json)",
    )
    args = p.parse_args()
    if args.from_mock or not args.pair:
        pairs = mock_pairs()
    else:
        pairs = []
        for t in args.pair:
            a, _, b = t.partition("|")
            if not b:
                print("Need Name|BaseType: " + t, file=sys.stderr)
                return 2
            pairs.append((a.strip(), b.strip()))
    entries: list[dict] = []
    for name, base in pairs:
        s = slug(name)
        u = f"https://poe2db.tw/us/{urllib.parse.quote(s, safe=':%/_+')}"
        time.sleep(args.delay)
        try:
            html_ = http_get(u)
        except OSError as e:
            print(f"FAIL {name} {e}", file=sys.stderr)
            continue
        j = extract_json(html_) or {}
        if j.get("name") and j.get("name") != name:
            print(
                f"WARN name: page JSON {j.get('name')!r} != {name!r} slug {s!r} {u}",
                file=sys.stderr,
            )
        hints = build_hints(html_)
        btype = j.get("baseType") or j.get("typeLine") or ""
        ent: dict = {"name": name, "base_type": base or (btype or "")}
        f = jflav(j) if j else None
        if f:
            ent["flavour"] = f
        if hints:
            ent["mod_range_hints"] = hints
        if not f and not hints:
            print(f"EMPTY {name!r} — add manually; {u}", file=sys.stderr)
        entries.append(ent)
    data = {"entries": entries}
    s = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    if args.out is not None:
        args.out.write_text(s, encoding="utf-8")
    sys.stdout.write(s)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
