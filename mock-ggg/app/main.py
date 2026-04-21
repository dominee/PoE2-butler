"""Mock GGG OAuth2 + API.

Loose emulation of GGG's OAuth2 and account endpoints against local fixture data.
The shape of each endpoint mirrors the real GGG API as used by
``backend/app/clients/ggg_client.py``.  Real paths will be confirmed once GGG
approves the client; adjustments here must be mirrored in the backend client.

This service MUST NOT be exposed outside development networks.
"""

from __future__ import annotations

import json
import secrets
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from fastapi import FastAPI, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

app = FastAPI(title="Mock GGG", version="0.1.0")

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str) -> dict[str, Any]:
    with (FIXTURES / name).open("r", encoding="utf-8") as f:
        return json.load(f)


USERS = _load("users.json")
CHARACTERS = _load("characters.json")
STASHES = _load("stashes.json")

# In-memory stores for auth flow artefacts. Fine for a dev mock.
PENDING_AUTH: dict[str, dict[str, Any]] = {}
ACCESS_TOKENS: dict[str, dict[str, Any]] = {}
REFRESH_TOKENS: dict[str, dict[str, Any]] = {}

# Per-tab call counter: first call returns prev_contents (if present), later
# calls return the full contents.  Simulates items arriving between snapshots,
# which populates the activity log on the second Refresh.
_TAB_CALL_COUNT: dict[str, int] = {}


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/dev/reset-activity", response_class=HTMLResponse)
async def reset_activity() -> HTMLResponse:
    """Reset the stash-tab call counters so the activity simulation restarts."""
    _TAB_CALL_COUNT.clear()
    return HTMLResponse(
        """<!doctype html><html><body style="font-family:system-ui;background:#1a1a1a;color:#eee;padding:2rem">
        <h2 style="color:#8f8">Activity simulation reset ✓</h2>
        <p>Stash tab counters cleared. The next refresh in the app will store the
        <em>previous</em> (smaller) snapshot, and the subsequent Refresh will
        detect the new items.</p>
        </body></html>"""
    )


# --- OAuth2 endpoints ---------------------------------------------------------


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


@app.post("/oauth/authorize")
async def authorize_submit(request_id: str = Form(...), user: str = Form(...)) -> RedirectResponse:
    pending = PENDING_AUTH.pop(request_id, None)
    if pending is None:
        raise HTTPException(400, "unknown_or_expired_request")
    if user not in USERS:
        raise HTTPException(400, "unknown_user")

    code = secrets.token_urlsafe(24)
    PENDING_AUTH[code] = {**pending, "user": user, "issued_at": time.time()}

    params = urlencode({"code": code, "state": pending["state"]})
    return RedirectResponse(f"{pending['redirect_uri']}?{params}", status_code=302)


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
    return JSONResponse({"revoked": True})


# --- Resource endpoints -------------------------------------------------------


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
async def characters(request: Request) -> JSONResponse:
    user = _require_user(request)
    return JSONResponse({"characters": USERS[user]["characters"]})


@app.get("/account/characters/{name}")
async def character(name: str, request: Request) -> JSONResponse:
    _require_user(request)
    if name not in CHARACTERS:
        raise HTTPException(404, "not_found")
    return JSONResponse(CHARACTERS[name])


@app.get("/account/stashes/{league}")
async def stash_tabs(league: str, request: Request) -> JSONResponse:
    _require_user(request)
    data = STASHES.get(league)
    if data is None:
        return JSONResponse({"tabs": []})
    return JSONResponse({"tabs": data["tabs"]})


@app.get("/account/stashes/{league}/{tab_id}")
async def stash_tab(league: str, tab_id: str, request: Request) -> JSONResponse:
    _require_user(request)
    data = STASHES.get(league)
    if data is None or tab_id not in data["contents"]:
        raise HTTPException(404, "not_found")

    key = f"{league}/{tab_id}"
    call_n = _TAB_CALL_COUNT.get(key, 0)
    _TAB_CALL_COUNT[key] = call_n + 1

    # First call: return prev_contents if available (simulates "before refresh" state).
    # Subsequent calls: return the full current contents.
    if call_n == 0 and "prev_contents" in data and tab_id in data["prev_contents"]:
        return JSONResponse(data["prev_contents"][tab_id])

    return JSONResponse(data["contents"][tab_id])
