"""Fetch Poe.ninja character snapshots (events → model)."""

from __future__ import annotations

import os
import time
from typing import Any

import httpx

from ninja_convert import ninja_model_body_to_ggg, stable_id
from ninja_urls import NinjaCharacterRef

NINJA_BASE = "https://poe.ninja"


def poe_ninja_read_timeout() -> httpx.Timeout:
    """Large reads (model JSON); keep below Traefik but above slow Poe.ninja responses."""
    return httpx.Timeout(120.0, connect=30.0)


def _min_interval_between_requests_sec() -> float:
    """Poe.ninja is a shared public API — stay conservative (configurable)."""
    raw = (os.environ.get("MOCK_GGG_POE_NINJA_MIN_INTERVAL_SEC") or "").strip()
    if raw:
        try:
            return max(0.0, float(raw))
        except ValueError:
            pass
    return 0.75


def _rate_limit_sleep() -> None:
    delay = _min_interval_between_requests_sec()
    if delay > 0:
        time.sleep(delay)


def _extract_version(body: dict[str, Any]) -> int:
    data = body.get("data")
    if isinstance(data, dict) and "version" in data:
        return int(data["version"])
    if "version" in body:
        return int(body["version"])
    raise ValueError("poe_ninja_events_missing_version")


def fetch_events_version(client: httpx.Client, ref: NinjaCharacterRef) -> int:
    url = (
        f"{NINJA_BASE}/poe2/api/events/character/"
        f"{ref.account}/{ref.league_slug}/{ref.character_name}"
    )
    r = client.get(url, timeout=poe_ninja_read_timeout())
    r.raise_for_status()
    body = r.json()
    _rate_limit_sleep()
    if not isinstance(body, dict):
        raise ValueError("poe_ninja_events_invalid_json")
    return _extract_version(body)


def fetch_model_body(client: httpx.Client, ref: NinjaCharacterRef, version: int) -> dict[str, Any]:
    url = (
        f"{NINJA_BASE}/poe2/api/profile/characters/"
        f"{ref.account}/{ref.league_slug}/{ref.character_name}/model/{version}"
    )
    r = client.get(url, timeout=poe_ninja_read_timeout())
    r.raise_for_status()
    body = r.json()
    _rate_limit_sleep()
    if not isinstance(body, dict):
        raise ValueError("poe_ninja_model_invalid_json")
    return body


def fetch_character_ggg(client: httpx.Client, ref: NinjaCharacterRef) -> dict[str, Any]:
    version = fetch_events_version(client, ref)
    body = fetch_model_body(client, ref, version)
    return ninja_model_body_to_ggg(body)


def fetch_character_ggg_and_account(
    client: httpx.Client, ref: NinjaCharacterRef
) -> tuple[dict[str, Any], str | None]:
    version = fetch_events_version(client, ref)
    body = fetch_model_body(client, ref, version)
    ggg = ninja_model_body_to_ggg(body)
    cm = body.get("charModel")
    acct = cm.get("account") if isinstance(cm, dict) else None
    return ggg, acct if isinstance(acct, str) else None


def account_slug_to_user_id(slug: str) -> str:
    return slug.replace(".", "_").replace("-", "_")


def league_name_from_url_slug(slug: str) -> str:
    s = (slug or "").lower()
    if s == "vaal":
        return "Fate of the Vaal"
    return slug


def synthetic_character_summaries(refs: list[NinjaCharacterRef]) -> list[dict[str, Any]]:
    """Fast OAuth/callback list before live Poe.ninja data is available."""
    out: list[dict[str, Any]] = []
    for ref in refs:
        key = f"{ref.account}:{ref.character_name}"
        out.append(
            {
                "id": stable_id(key),
                "name": ref.character_name,
                "realm": "pc",
                "class": "Pending",
                "level": 1,
                "league": league_name_from_url_slug(ref.league_slug),
                "experience": 0,
            }
        )
    return out


def build_leagues_payload(league_ids: set[str]) -> list[dict[str, Any]]:
    """Synthetic league list for mock profile (mirrors prior fixture style)."""
    if not league_ids:
        return []

    if "Fate of the Vaal" in league_ids:
        preferred = "Fate of the Vaal"
    else:
        non_hc = [L for L in league_ids if not str(L).startswith("Hardcore")]
        preferred = sorted(non_hc or list(league_ids))[0]

    rows: list[dict[str, Any]] = []
    if "Standard" not in league_ids:
        rows.append({"id": "Standard", "realm": "pc", "description": "Standard", "current": False})
    for lid in sorted(league_ids):
        rows.append(
            {
                "id": lid,
                "realm": "pc",
                "description": lid,
                "current": lid == preferred,
            }
        )
    return rows


def character_summary(ggg: dict[str, Any]) -> dict[str, Any]:
    ch = ggg["character"]
    return {
        "id": ch["id"],
        "name": ch["name"],
        "realm": ch.get("realm", "pc"),
        "class": ch["class"],
        "level": ch["level"],
        "league": ch["league"],
        "experience": ch.get("experience", 0),
    }


def build_user_blob_from_ggg(
    *,
    profile_display_name: str,
    summaries: list[dict[str, Any]],
    league_ids: set[str],
) -> dict[str, Any]:
    return {
        "profile": {
            "name": profile_display_name,
            "uuid": stable_id(profile_display_name),
            "realm": "pc",
            "guild": None,
        },
        "leagues": build_leagues_payload(league_ids),
        "characters": summaries,
    }
