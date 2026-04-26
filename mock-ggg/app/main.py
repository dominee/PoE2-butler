"""Mock GGG OAuth2 + API.

Loose emulation of GGG's OAuth2 and account endpoints against local fixture data
and (optionally) live Poe.ninja character snapshots configured via TOML.

This service MUST NOT be exposed outside development networks.
"""

from __future__ import annotations

import copy
import json
import logging
import os
import secrets
import sys
import time
import asyncio
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import httpx
from fastapi import FastAPI, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from starlette.concurrency import run_in_threadpool

_APP_DIR = Path(__file__).resolve().parent
if str(_APP_DIR) not in sys.path:
    sys.path.insert(0, str(_APP_DIR))

from ninja_config import load_character_refs
from ninja_convert import pack_items, stable_id
from ninja_urls import NinjaCharacterRef
from poe_ninja import (
    account_slug_to_user_id,
    build_leagues_payload,
    build_user_blob_from_ggg,
    character_summary,
    fetch_character_ggg_and_account,
    league_name_from_url_slug,
    poe_ninja_read_timeout,
    synthetic_character_summaries,
)

log = logging.getLogger(__name__)


def _poe_ninja_network_disabled() -> bool:
    """When true: no live Poe.ninja HTTP (backend tests); TOML still drives OAuth user ids."""
    return os.environ.get("MOCK_GGG_SKIP_POE_NINJA") == "1"


FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str) -> dict[str, Any]:
    with (FIXTURES / name).open("r", encoding="utf-8") as f:
        return json.load(f)


def _group_ninja_refs(refs: list[NinjaCharacterRef]) -> dict[str, list[NinjaCharacterRef]]:
    m: dict[str, list[NinjaCharacterRef]] = {}
    for ref in refs:
        uid = account_slug_to_user_id(ref.account)
        m.setdefault(uid, []).append(ref)
    return m


try:
    _ninja_url_refs = load_character_refs()
except Exception as exc:
    log.warning("mock_ggg: failed to load poe_ninja character TOML (%s)", exc)
    _ninja_url_refs = []
NINJA_REFS_BY_USER: dict[str, list[NinjaCharacterRef]] = _group_ninja_refs(_ninja_url_refs)

USERS: dict[str, Any] = dict(_load("static_users.json"))
# Optional static OAuth rows; TOML accounts are merged below. Fixture blobs in characters.json seed ninja detail when not hitting Poe.ninja.
FIXTURE_CHARACTERS: dict[str, Any] = _load("characters.json")
STASHES: dict[str, Any] = _load("stashes.json")
# OAuth user id -> character name -> GGG-style detail (never share across mock users).
_character_detail_by_user: dict[str, dict[str, Any]] = {}

for _nuid in NINJA_REFS_BY_USER:
    if _nuid not in USERS:
        USERS[_nuid] = {
            "profile": {"name": _nuid, "uuid": stable_id(_nuid), "realm": "pc", "guild": None},
            "leagues": [],
            "characters": [],
        }

PENDING_AUTH: dict[str, dict[str, Any]] = {}
# Idempotent authorize POST: double-submit / back+resubmit reuses the same redirect briefly.
_RECENT_AUTHORIZE_REDIRECT: dict[str, str] = {}
_authorize_post_lock = asyncio.Lock()
ACCESS_TOKENS: dict[str, dict[str, Any]] = {}
REFRESH_TOKENS: dict[str, dict[str, Any]] = {}
# Coalesce concurrent GETs for the same (user, character) while Poe.ninja runs once.
_character_fetch_locks: dict[tuple[str, str], asyncio.Lock] = {}
# Startup warm (lifespan): one asyncio task per ninja OAuth uid (parallel Poe.ninja account syncs).
_ninja_warm_task: asyncio.Task[None] | None = None
_ninja_warm_by_uid: dict[str, asyncio.Task[None]] = {}


def _character_startup_warm_wait_budget_sec() -> float:
    """How long GET /account/characters/{name} may wait for this user's Poe.ninja warm task.

    The warm task fetches *every* character on the account sequentially; waiting for it to
    finish blocks the gear screen for minutes. A short budget lets the handler fall through
    to a per-character Poe.ninja fetch for the requested name while warm continues in the
    background (warm may duplicate work for that ref — acceptable).
    """
    raw = (os.environ.get("MOCK_GGG_CHARACTER_WARM_WAIT_SEC") or "5").strip()
    try:
        v = float(raw)
    except ValueError:
        v = 5.0
    return max(0.0, min(v, 600.0))


def _character_fetch_lock(uid: str, char_name: str) -> asyncio.Lock:
    key = (uid, char_name)
    lock = _character_fetch_locks.get(key)
    if lock is None:
        lock = asyncio.Lock()
        _character_fetch_locks[key] = lock
    return lock


def _character_detail_for_user(uid: str, name: str) -> Any | None:
    per = _character_detail_by_user.get(uid)
    if per is not None and name in per:
        return per[name]
    return None


def _put_character_detail(uid: str, name: str, ggg: dict[str, Any]) -> None:
    _character_detail_by_user.setdefault(uid, {})[name] = ggg


def _has_character_detail(uid: str, name: str) -> bool:
    return _character_detail_for_user(uid, name) is not None


def _character_needs_poe_ninja_fill(uid: str, name: str) -> bool:
    """True when detail is missing or still the empty-gear bootstrap stub.

    Bootstrap seeds ``items: []`` so ``_has_character_detail`` is true; without this,
    GET /account/characters/{name} would never scrape Poe.ninja and the doll stays empty.
    """
    d = _character_detail_for_user(uid, name)
    if d is None:
        return True
    items = d.get("items") if isinstance(d, dict) else None
    return isinstance(items, list) and len(items) == 0


def _minimal_ggg_character(ref: NinjaCharacterRef) -> dict[str, Any]:
    """Valid empty-gear payload until Poe.ninja warm or on-demand fetch replaces it."""
    league = league_name_from_url_slug(ref.league_slug)
    return {
        "character": {
            "id": stable_id(f"{ref.account}:{ref.character_name}"),
            "name": ref.character_name,
            "realm": "pc",
            "class": "Scion",
            "level": 1,
            "league": league,
            "experience": 0,
        },
        "items": [],
    }


def _bootstrap_ninja_mock_users() -> None:
    """Synthetic leagues + character detail seeds so dev works before background Poe.ninja warm.

    - ``/account/leagues`` is non-empty (GGG snapshot + UI league dropdown).
    - Character detail GET returns immediately (fixture copy or minimal stub); warm overwrites.
    """
    if not NINJA_REFS_BY_USER:
        return
    for uid, refs in NINJA_REFS_BY_USER.items():
        league_ids = {league_name_from_url_slug(r.league_slug) for r in refs}
        rows = build_leagues_payload(league_ids)
        if rows:
            USERS[uid]["leagues"] = rows

        for ref in refs:
            if _has_character_detail(uid, ref.character_name):
                continue
            blob = FIXTURE_CHARACTERS.get(ref.character_name)
            if blob is not None:
                _put_character_detail(uid, ref.character_name, copy.deepcopy(blob))
            else:
                _put_character_detail(uid, ref.character_name, _minimal_ggg_character(ref))


_bootstrap_ninja_mock_users()

_token_path = (os.environ.get("MOCK_GGG_TOKEN_FILE") or "").strip()
_TOKEN_FILE: str | None = _token_path or None


def _apply_ninja_slug_identity(ref: NinjaCharacterRef, ggg: dict[str, Any]) -> None:
    """Align ``character.name`` / ``id`` with the TOML URL slug (Poe charModel ``name`` can differ, e.g. ``Big BMaru`` vs ``Big_BMaru``)."""
    ch = ggg.get("character")
    if not isinstance(ch, dict):
        return
    ch["name"] = ref.character_name
    ch["id"] = stable_id(f"{ref.account}:{ref.character_name}")


def _run_warm_uid_in_thread(uid: str, refs: list[NinjaCharacterRef]) -> None:
    """Thread entry for startup warm (must open its own ``httpx.Client``)."""
    with httpx.Client(timeout=poe_ninja_read_timeout()) as client:
        _sync_ninja_user_with_client(uid, refs, client)


def _sync_ninja_user_with_client(uid: str, refs: list[NinjaCharacterRef], client: httpx.Client) -> None:
    summaries: list[dict[str, Any]] = []
    league_ids: set[str] = set()
    profile_name: str | None = None
    for ref in refs:
        ggg, acct = fetch_character_ggg_and_account(client, ref)
        poe_name = str(ggg.get("character", {}).get("name") or ref.character_name)
        _apply_ninja_slug_identity(ref, ggg)
        _put_character_detail(uid, ref.character_name, ggg)
        if poe_name != ref.character_name:
            _put_character_detail(uid, poe_name, ggg)
        summaries.append(character_summary(ggg))
        league_ids.add(str(ggg["character"]["league"]))
        if acct:
            profile_name = acct
    USERS[uid] = build_user_blob_from_ggg(
        profile_display_name=profile_name or uid,
        summaries=summaries,
        league_ids=league_ids,
    )


def _revalidate_ninja_characters_sync(uid: str, refs: list[NinjaCharacterRef]) -> None:
    with httpx.Client(timeout=poe_ninja_read_timeout()) as client:
        _sync_ninja_user_with_client(uid, refs, client)


def _sync_ninja_character_detail_sync(
    uid: str, char_name: str, refs: list[NinjaCharacterRef]
) -> None:
    with httpx.Client(timeout=poe_ninja_read_timeout()) as client:
        _sync_ninja_character_detail(uid, char_name, refs, client)


def _ref_for_character_name(refs: list[NinjaCharacterRef], char_name: str) -> NinjaCharacterRef | None:
    """Match TOML slug to roster name (spacing / underscores differ from Poe display names)."""
    for r in refs:
        if r.character_name == char_name:
            return r
    norm = char_name.replace(" ", "_")
    for r in refs:
        if r.character_name.replace(" ", "_") == norm:
            return r
    lowered = char_name.lower()
    for r in refs:
        if r.character_name.lower() == lowered:
            return r
    return None


def _sync_ninja_character_detail(
    uid: str, char_name: str, refs: list[NinjaCharacterRef], client: httpx.Client
) -> None:
    ref = _ref_for_character_name(refs, char_name)
    if ref is None:
        return
    ggg, _ = fetch_character_ggg_and_account(client, ref)
    poe_name = str(ggg.get("character", {}).get("name") or ref.character_name)
    _apply_ninja_slug_identity(ref, ggg)
    _put_character_detail(uid, ref.character_name, ggg)
    if poe_name != ref.character_name:
        _put_character_detail(uid, poe_name, ggg)
    blob = USERS.get(uid)
    chars = blob.get("characters") if isinstance(blob, dict) else None
    if isinstance(chars, list):
        ns = character_summary(ggg)
        blob["characters"] = [
            ns if isinstance(c, dict) and c.get("name") in (char_name, ref.character_name) else c
            for c in chars
        ]


async def _background_ninja_warm() -> None:
    """One Poe.ninja sync per ninja account, in parallel (each uid still serializes its own chars)."""
    global _ninja_warm_by_uid
    _ninja_warm_by_uid.clear()
    if not NINJA_REFS_BY_USER:
        return
    try:
        for uid, refs in NINJA_REFS_BY_USER.items():
            _ninja_warm_by_uid[uid] = asyncio.create_task(
                run_in_threadpool(_run_warm_uid_in_thread, uid, refs),
                name=f"mock_ggg_poe_ninja_warm:{uid}",
            )
        results = await asyncio.gather(*_ninja_warm_by_uid.values(), return_exceptions=True)
        for uid, res in zip(_ninja_warm_by_uid.keys(), results, strict=True):
            if isinstance(res, BaseException):
                log.warning("mock_ggg: poe.ninja warm failed for %s (%s)", uid, res)
        log.info("mock_ggg: background poe.ninja sync finished (%d accounts)", len(_ninja_warm_by_uid))
    except Exception as exc:
        log.warning("mock_ggg: background poe.ninja sync failed (%s)", exc)


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    """Start Poe.ninja warm-up without blocking readiness (rate limits apply inside the thread)."""
    global _ninja_warm_task
    _ninja_warm_task = None
    if NINJA_REFS_BY_USER and not _poe_ninja_network_disabled():
        _ninja_warm_task = asyncio.create_task(_background_ninja_warm(), name="mock_ggg_poe_ninja_warm")
    yield
    if _ninja_warm_task is not None and not _ninja_warm_task.done():
        for _child in list(_ninja_warm_by_uid.values()):
            if not _child.done():
                _child.cancel()
        try:
            await asyncio.wait_for(_ninja_warm_task, timeout=120.0)
        except TimeoutError:
            log.warning("mock_ggg: background poe.ninja sync still running at shutdown; cancelling")
            _ninja_warm_task.cancel()
            with suppress(asyncio.CancelledError):
                await _ninja_warm_task


app = FastAPI(title="Mock GGG", version="0.1.0", lifespan=_lifespan)


def _persist_token_maps() -> None:
    if not _TOKEN_FILE:
        return
    try:
        path = Path(_TOKEN_FILE)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"access": ACCESS_TOKENS, "refresh": REFRESH_TOKENS}
        path.write_text(json.dumps(payload), encoding="utf-8")
    except OSError:
        pass


def _load_token_maps() -> None:
    if not _TOKEN_FILE:
        return
    path = Path(_TOKEN_FILE)
    if not path.is_file():
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return
    a = data.get("access")
    r = data.get("refresh")
    if isinstance(a, dict):
        ACCESS_TOKENS.clear()
        for k, v in a.items():
            if isinstance(k, str) and isinstance(v, dict):
                ACCESS_TOKENS[k] = v
    if isinstance(r, dict):
        REFRESH_TOKENS.clear()
        for k, v in r.items():
            if isinstance(k, str) and isinstance(v, dict):
                REFRESH_TOKENS[k] = v


_load_token_maps()

_TAB_CALL_COUNT: dict[str, int] = {}

# GGG inventory slots we mirror into the mock stash "gear summary" tab (gear + flasks + jewels).
_GGG_STASH_EQUIP_SLOTS = frozenset(
    {
        "Weapon",
        "Weapon2",
        "Offhand",
        "Offhand2",
        "Helm",
        "BodyArmour",
        "Gloves",
        "Boots",
        "Amulet",
        "Ring",
        "Ring2",
        "Belt",
        "Flask",
        "PassiveJewels",
    }
)


def _equipped_items_for_ninja_stash(user: str, league: str) -> list[dict[str, Any]]:
    """Collect equipped rows from character detail for every TOML character in this league."""
    refs = NINJA_REFS_BY_USER.get(user) or []
    out: list[dict[str, Any]] = []
    for ref in refs:
        if league_name_from_url_slug(ref.league_slug) != league:
            continue
        detail = _character_detail_for_user(user, ref.character_name)
        if not isinstance(detail, dict):
            continue
        char_key = stable_id(f"{ref.account}:{ref.character_name}")[:10]
        for raw in detail.get("items") or []:
            if not isinstance(raw, dict):
                continue
            if raw.get("inventoryId") not in _GGG_STASH_EQUIP_SLOTS:
                continue
            item = copy.deepcopy(raw)
            orig_id = item.get("id")
            if orig_id is not None:
                item["id"] = f"{char_key}-{orig_id}"
            item.pop("x", None)
            item.pop("y", None)
            out.append(item)
    return out


def _ninja_stash_from_equipped(user: str, league: str) -> dict[str, Any] | None:
    """Same tab ids as the fixture league; first tab holds packed equipped gear for this account."""
    base = STASHES.get(league)
    if not isinstance(base, dict):
        return None
    tabs = copy.deepcopy(base.get("tabs") or [])
    raw_items = _equipped_items_for_ninja_stash(user, league)
    try:
        packed = pack_items(raw_items) if raw_items else []
    except Exception as exc:
        log.warning("mock_ggg: pack_items failed for equipped summary (%s)", exc)
        packed = []

    tab_ids = [t["id"] for t in tabs if isinstance(t, dict) and isinstance(t.get("id"), str)]
    first_id = tab_ids[0] if tab_ids else "fate-of-the-vaal-gear"
    contents: dict[str, Any] = {}
    prev_contents: dict[str, Any] = {}
    for tid in tab_ids:
        block = packed if tid == first_id else []
        contents[tid] = {"items": block}
        # First GET serves ``prev_contents`` (see stash_tab); keep populated like static STASHES fixtures.
        prev_contents[tid] = {"items": copy.deepcopy(block)}
    return {"tabs": tabs, "contents": contents, "prev_contents": prev_contents}


def _stash_dataset_for_user(user: str, league: str) -> dict[str, Any] | None:
    """Ninja accounts: stash derived from equipped items (no shared druid fixture)."""
    if user in NINJA_REFS_BY_USER:
        return _ninja_stash_from_equipped(user, league)
    return STASHES.get(league)


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/dev/reset-activity", response_class=HTMLResponse)
async def reset_activity() -> HTMLResponse:
    _TAB_CALL_COUNT.clear()
    return HTMLResponse(
        """<!doctype html><html><body style="font-family:system-ui;background:#1a1a1a;color:#eee;padding:2rem">
        <h2 style="color:#8f8">Activity simulation reset ✓</h2>
        <p>Stash tab counters cleared. The next refresh in the app will store the
        <em>previous</em> (smaller) snapshot, and the subsequent Refresh will
        detect the new items.</p>
        </body></html>"""
    )


@app.get("/oauth/authorize", response_class=HTMLResponse)
async def authorize(
    response_type: str = Query(...),
    client_id: str = Query(...),
    redirect_uri: str = Query(...),
    scope: str = Query(...),
    state: str = Query(...),
    code_challenge: str = Query(...),
    code_challenge_method: str = Query(...),
) -> HTMLResponse:
    if response_type != "code":
        raise HTTPException(400, "unsupported_response_type")
    if code_challenge_method != "S256":
        raise HTTPException(400, "unsupported_challenge_method")

    request_id = secrets.token_urlsafe(12)
    PENDING_AUTH[request_id] = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": scope,
        "state": state,
        "code_challenge": code_challenge,
    }

    options = "".join(
        f'<option value="{uid}">{uid} ({data["profile"]["name"]})</option>'
        for uid, data in USERS.items()
    )
    html = f"""<!doctype html>
<html><head><title>Mock GGG Authorize</title>
<style>
  body {{ font-family: system-ui; background: #1a1a1a; color: #eee; padding: 2rem; }}
  form {{ background: #2a2a2a; padding: 2rem; border-radius: 8px; max-width: 480px; }}
  label {{ display: block; margin: 1rem 0 0.25rem; }}
  select, button {{ width: 100%; padding: 0.5rem; font-size: 1rem; }}
  button {{ margin-top: 1.5rem; background: #c8a040; border: 0; color: #1a1a1a; cursor: pointer; }}
  small {{ color: #888; display: block; margin-top: 1rem; }}
  .hint {{ background: #1e2a1e; border: 1px solid #2a4a2a; border-radius: 6px; padding: 0.75rem; margin-top: 1.5rem; font-size: 0.8rem; color: #8a8; }}
</style></head>
<body>
  <h1>Mock GGG sign-in</h1>
  <form method="post" action="/oauth/authorize">
    <input type="hidden" name="request_id" value="{request_id}"/>
    <label for="user">Sign in as</label>
    <select name="user" id="user">{options}</select>
    <button type="submit">Authorize</button>
    <small>client_id: {client_id}<br/>scope: {scope}</small>
  </form>
  <div class="hint">
    <strong>Activity log tip:</strong> After signing in, click <em>Refresh</em> once
    in the app to populate the activity log with new items detected since the initial snapshot.
    To re-run the simulation, visit <a href="/dev/reset-activity" style="color:#8f8">/dev/reset-activity</a>.
  </div>
</body></html>"""
    return HTMLResponse(html)


async def _expire_recent_authorize_redirect(request_id: str, delay: float) -> None:
    await asyncio.sleep(delay)
    _RECENT_AUTHORIZE_REDIRECT.pop(request_id, None)


@app.post("/oauth/authorize")
async def authorize_submit(request_id: str = Form(...), user: str = Form(...)) -> RedirectResponse:
    async with _authorize_post_lock:
        pending = PENDING_AUTH.get(request_id)
        if pending is None:
            replay = _RECENT_AUTHORIZE_REDIRECT.get(request_id)
            if replay is not None:
                return RedirectResponse(replay, status_code=302)
            raise HTTPException(400, "unknown_or_expired_request")
        if user not in USERS:
            raise HTTPException(400, "unknown_user")

        PENDING_AUTH.pop(request_id, None)
        code = secrets.token_urlsafe(24)
        PENDING_AUTH[code] = {**pending, "user": user, "issued_at": time.time()}

        params = urlencode({"code": code, "state": pending["state"]})
        loc = f"{pending['redirect_uri']}?{params}"
        _RECENT_AUTHORIZE_REDIRECT[request_id] = loc
    asyncio.create_task(_expire_recent_authorize_redirect(request_id, 120.0))
    return RedirectResponse(loc, status_code=302)


@app.post("/oauth/token")
async def token(
    grant_type: str = Form(...),
    code: str | None = Form(None),
    redirect_uri: str | None = Form(None),
    client_id: str | None = Form(None),
    client_secret: str | None = Form(None),
    code_verifier: str | None = Form(None),
    refresh_token: str | None = Form(None),
) -> JSONResponse:
    if grant_type == "authorization_code":
        if code is None or code_verifier is None:
            raise HTTPException(400, "missing_code_or_verifier")
        pending = PENDING_AUTH.pop(code, None)
        if pending is None:
            raise HTTPException(400, "invalid_grant")

        access = secrets.token_urlsafe(32)
        refresh = secrets.token_urlsafe(32)
        ACCESS_TOKENS[access] = {"user": pending["user"], "expires_at": time.time() + 3600}
        REFRESH_TOKENS[refresh] = {"user": pending["user"], "scope": pending["scope"]}

        _persist_token_maps()
        return JSONResponse(
            {
                "access_token": access,
                "refresh_token": refresh,
                "token_type": "Bearer",
                "expires_in": 3600,
                "scope": pending["scope"],
            }
        )

    if grant_type == "refresh_token":
        if refresh_token is None or refresh_token not in REFRESH_TOKENS:
            raise HTTPException(400, "invalid_grant")
        rt = REFRESH_TOKENS[refresh_token]
        access = secrets.token_urlsafe(32)
        ACCESS_TOKENS[access] = {"user": rt["user"], "expires_at": time.time() + 3600}
        _persist_token_maps()
        return JSONResponse(
            {
                "access_token": access,
                "token_type": "Bearer",
                "expires_in": 3600,
                "scope": rt["scope"],
            }
        )

    raise HTTPException(400, "unsupported_grant_type")


@app.post("/oauth/revoke")
async def revoke(token: str = Form(...)) -> JSONResponse:
    ACCESS_TOKENS.pop(token, None)
    REFRESH_TOKENS.pop(token, None)
    _persist_token_maps()
    return JSONResponse({"revoked": True})


def _require_user(request: Request) -> str:
    auth = request.headers.get("authorization", "")
    if not auth.lower().startswith("bearer "):
        raise HTTPException(401, "missing_bearer")
    tok = auth.split(" ", 1)[1].strip()
    entry = ACCESS_TOKENS.get(tok)
    if entry is None or entry["expires_at"] < time.time():
        raise HTTPException(401, "invalid_token")
    return entry["user"]


@app.get("/profile")
async def profile(request: Request) -> JSONResponse:
    user = _require_user(request)
    return JSONResponse(USERS[user]["profile"])


@app.get("/account/leagues")
async def leagues(request: Request) -> JSONResponse:
    user = _require_user(request)
    return JSONResponse({"leagues": USERS[user]["leagues"]})


@app.get("/account/characters")
async def characters(
    request: Request,
    revalidate: bool = Query(False, description="When true, refetch all Poe.ninja models (slow)."),
) -> JSONResponse:
    """OAuth callback must stay fast: default path serves cache or URL-derived placeholders."""
    user = _require_user(request)
    refs = NINJA_REFS_BY_USER.get(user)
    if refs and revalidate and not _poe_ninja_network_disabled():
        try:
            await run_in_threadpool(_revalidate_ninja_characters_sync, user, refs)
        except Exception as exc:
            log.warning("mock_ggg: character list revalidate failed (%s)", exc)
    blob = USERS.get(user) or {}
    ch = blob.get("characters")
    if isinstance(ch, list) and len(ch) > 0:
        return JSONResponse({"characters": ch})
    if refs:
        return JSONResponse({"characters": synthetic_character_summaries(refs)})
    return JSONResponse({"characters": ch if isinstance(ch, list) else []})


@app.get("/account/characters/{name}")
async def character(
    name: str,
    request: Request,
    revalidate: bool = Query(
        False,
        description="When true, refetch this character from Poe.ninja (slow). Default serves cache.",
    ),
) -> JSONResponse:
    user = _require_user(request)
    refs = NINJA_REFS_BY_USER.get(user)
    # Poe.ninja is slow; never refetch on every GET (that starved the app + proxies).
    if refs and (revalidate or _character_needs_poe_ninja_fill(user, name)) and not _poe_ninja_network_disabled():
        lock = _character_fetch_lock(user, name)
        async with lock:
            if revalidate or _character_needs_poe_ninja_fill(user, name):
                wt = _ninja_warm_by_uid.get(user)
                if (
                    wt is not None
                    and not wt.done()
                    and not revalidate
                    and _character_needs_poe_ninja_fill(user, name)
                ):
                    budget = _character_startup_warm_wait_budget_sec()
                    if budget > 0:
                        try:
                            await asyncio.wait_for(wt, timeout=budget)
                        except TimeoutError:
                            log.warning(
                                "mock_ggg: startup poe.ninja warm still running after %.1fs; per-char fetch for %r",
                                budget,
                                name,
                            )
                        except asyncio.CancelledError:
                            pass
                        except Exception as exc:
                            log.warning(
                                "mock_ggg: startup warm task for %s finished with error (%s); per-char fetch may run",
                                user,
                                exc,
                            )
                if revalidate or _character_needs_poe_ninja_fill(user, name):
                    try:
                        await run_in_threadpool(_sync_ninja_character_detail_sync, user, name, refs)
                    except httpx.HTTPError as exc:
                        log.warning("mock_ggg: poe.ninja character %r failed (%s)", name, exc)
                        if not _has_character_detail(user, name):
                            raise HTTPException(
                                status_code=503, detail="poe_ninja_unavailable"
                            ) from exc
                    except Exception as exc:
                        log.warning("mock_ggg: poe.ninja character %r failed (%s)", name, exc)
                        if not _has_character_detail(user, name):
                            raise HTTPException(
                                status_code=503, detail="poe_ninja_unavailable"
                            ) from exc
    detail = _character_detail_for_user(user, name)
    if detail is None:
        raise HTTPException(404, "not_found")
    return JSONResponse(detail)


@app.get("/account/stashes/{league}")
async def stash_tabs(league: str, request: Request) -> JSONResponse:
    user = _require_user(request)
    data = _stash_dataset_for_user(user, league)
    if data is None:
        return JSONResponse({"tabs": []})
    return JSONResponse({"tabs": data["tabs"]})


@app.get("/account/stashes/{league}/{tab_id}")
async def stash_tab(league: str, tab_id: str, request: Request) -> JSONResponse:
    user = _require_user(request)
    data = _stash_dataset_for_user(user, league)
    if data is None or tab_id not in data.get("contents", {}):
        raise HTTPException(404, "not_found")

    key = f"{user}:{league}:{tab_id}"
    call_n = _TAB_CALL_COUNT.get(key, 0)
    _TAB_CALL_COUNT[key] = call_n + 1

    if call_n == 0 and "prev_contents" in data and tab_id in data["prev_contents"]:
        return JSONResponse(data["prev_contents"][tab_id])

    return JSONResponse(data["contents"][tab_id])
