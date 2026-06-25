"""Verify GGG OAuth2 client credentials and endpoint reachability.

Usage
-----
# Check config and print the authorization URL (no network calls to GGG):
    uv run python scripts/verify_ggg_oauth.py

# Also probe GGG endpoints with HTTP HEAD requests:
    uv run python scripts/verify_ggg_oauth.py --probe

# Full round-trip: exchange an authorization code for a token and call /profile.
# Obtain the code by visiting the printed authorization URL in a browser and
# copying the `code` query parameter from the redirect back to the app:
    uv run python scripts/verify_ggg_oauth.py --code <CODE> --code-verifier <VERIFIER>

The script exits with code 0 on success and 1 on any configuration or HTTP error.
It never logs client_secret or access_token values.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import os
import sys
from base64 import urlsafe_b64encode
from urllib.parse import urlencode

import httpx

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_REAL_GGG_OAUTH = "www.pathofexile.com"
_REAL_GGG_API = "api.pathofexile.com"


def _env(key: str, required: bool = True) -> str:
    val = os.environ.get(key, "")
    if required and not val:
        print(f"[ERROR] Environment variable {key} is not set.", file=sys.stderr)
        sys.exit(1)
    return val


def _assert_live_ggg() -> None:
    oauth_url = _env("GGG_OAUTH_BASE_URL")
    api_url = _env("GGG_API_BASE_URL")
    if _REAL_GGG_OAUTH not in oauth_url:
        print(
            f"[ERROR] GGG_OAUTH_BASE_URL={oauth_url!r} does not look like the real GGG endpoint.\n"
            "        Expected something containing 'www.pathofexile.com'.",
            file=sys.stderr,
        )
        sys.exit(1)
    if _REAL_GGG_API not in api_url:
        print(
            f"[ERROR] GGG_API_BASE_URL={api_url!r} does not look like the real GGG API.\n"
            "        Expected something containing 'api.pathofexile.com'.",
            file=sys.stderr,
        )
        sys.exit(1)


def _build_authorize_url() -> str:
    base = _env("GGG_OAUTH_AUTHORIZE_BASE_URL", required=False) or _env("GGG_OAUTH_BASE_URL")
    params = {
        "client_id": _env("GGG_CLIENT_ID"),
        "response_type": "code",
        "scope": _env("GGG_SCOPES"),
        "state": "verify-script-test-state",
        "redirect_uri": _env("GGG_REDIRECT_URI"),
        "code_challenge": urlsafe_b64encode(
            hashlib.sha256(b"verify-script-test-verifier").digest()
        )
        .rstrip(b"=")
        .decode(),
        "code_challenge_method": "S256",
    }
    return f"{base.rstrip('/')}/oauth/authorize?{urlencode(params)}"


# ---------------------------------------------------------------------------
# Async probes
# ---------------------------------------------------------------------------


async def probe_endpoints(oauth_base: str, api_base: str) -> bool:
    """HEAD-probe the token and profile endpoints; return True if all reachable."""
    checks = [
        (f"{oauth_base.rstrip('/')}/oauth/token", "token endpoint"),
        (f"{api_base.rstrip('/')}/profile", "profile endpoint"),
    ]
    ok = True
    async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
        for url, label in checks:
            try:
                r = await client.head(url)
                # 405 (Method Not Allowed) is fine — the endpoint exists.
                if r.status_code in (200, 405, 400):
                    print(f"  [OK]    {label}: {url}  →  HTTP {r.status_code}")
                else:
                    print(f"  [WARN]  {label}: {url}  →  HTTP {r.status_code} (unexpected)")
            except httpx.HTTPError as exc:
                print(f"  [FAIL]  {label}: {url}  →  {exc}", file=sys.stderr)
                ok = False
    return ok


async def exchange_and_verify(code: str, code_verifier: str) -> bool:
    """Exchange an authorization code for tokens and call GET /profile."""
    oauth_base = _env("GGG_OAUTH_BASE_URL")
    api_base = _env("GGG_API_BASE_URL")
    client_id = _env("GGG_CLIENT_ID")
    client_secret = _env("GGG_CLIENT_SECRET")
    redirect_uri = _env("GGG_REDIRECT_URI")

    token_url = f"{oauth_base.rstrip('/')}/oauth/token"
    profile_url = f"{api_base.rstrip('/')}/profile"

    ua = f"OAuth {client_id}/verify-script (contact: dev@hell.sk) PoE2-Hideout-Butler"

    print(f"\n[exchange] POST {token_url}")
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.post(
            token_url,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
                "code_verifier": code_verifier,
                "client_id": client_id,
                "client_secret": client_secret,
            },
            headers={"User-Agent": ua},
        )
        if r.status_code != 200:
            print(f"  [FAIL]  HTTP {r.status_code}: {r.text[:400]}", file=sys.stderr)
            return False
        body = r.json()
        scopes_received = body.get("scope", "")
        print(f"  [OK]    Token exchange succeeded. Scopes: {scopes_received!r}")

        access_token = body.get("access_token", "")
        if not access_token:
            print("  [FAIL]  No access_token in response.", file=sys.stderr)
            return False

        print(f"\n[profile] GET {profile_url}")
        rp = await client.get(
            profile_url,
            headers={"Authorization": f"Bearer {access_token}", "User-Agent": ua},
        )
        if rp.status_code != 200:
            print(f"  [FAIL]  HTTP {rp.status_code}: {rp.text[:400]}", file=sys.stderr)
            return False
        profile = rp.json()
        account_name = profile.get("name") or profile.get("uuid") or "(no name)"
        print(f"  [OK]    Profile fetched. Account: {account_name!r}")
    return True


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def main(args: argparse.Namespace) -> int:
    print("=== GGG OAuth2 Configuration Verification ===\n")

    # 1. Validate env vars are set and point to real GGG
    _assert_live_ggg()
    client_id = _env("GGG_CLIENT_ID")
    scopes = _env("GGG_SCOPES")
    redirect_uri = _env("GGG_REDIRECT_URI")
    oauth_base = _env("GGG_OAUTH_BASE_URL")
    api_base = _env("GGG_API_BASE_URL")

    print(f"  client_id   : {client_id}")
    print(f"  scopes      : {scopes}")
    print(f"  redirect_uri: {redirect_uri}")
    print(f"  oauth_base  : {oauth_base}")
    print(f"  api_base    : {api_base}")
    print()

    # 2. Print authorization URL
    auth_url = _build_authorize_url()
    print("[authorize URL]")
    print(f"  {auth_url}")
    print()

    # 3. Optional: probe endpoints
    if args.probe or args.code:
        print("[probing endpoints]")
        reachable = await probe_endpoints(oauth_base, api_base)
        if not reachable:
            print("\n[FAIL] One or more endpoints were unreachable.", file=sys.stderr)
            return 1
        print()

    # 4. Optional: full token exchange
    if args.code:
        if not args.code_verifier:
            print(
                "[ERROR] --code-verifier is required with --code.\n"
                "        (The verifier was generated by the backend during /api/auth/login;\n"
                "         for a quick test use 'verify-script-test-verifier'\n"
                "         if you visited the URL printed above.)",
                file=sys.stderr,
            )
            return 1
        ok = await exchange_and_verify(args.code, args.code_verifier)
        if not ok:
            print("\n[FAIL] Token exchange or profile call failed.", file=sys.stderr)
            return 1
        print("\n[OK] Full OAuth2 round-trip verified successfully.")
    else:
        print(
            "[INFO] Configuration looks valid. To do a full round-trip test:\n"
            "  1. Visit the authorize URL above in a browser.\n"
            "  2. Approve the application on GGG.\n"
            "  3. Copy the 'code' parameter from the redirect URL.\n"
            "  4. Run:  uv run python scripts/verify_ggg_oauth.py \\\n"
            "             --code <CODE> --code-verifier verify-script-test-verifier"
        )

    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Verify GGG OAuth2 client configuration.")
    parser.add_argument("--probe", action="store_true", help="HEAD-probe GGG endpoints.")
    parser.add_argument("--code", help="Authorization code from GGG callback (for full test).")
    parser.add_argument(
        "--code-verifier",
        help="PKCE code verifier that matches the code (use 'verify-script-test-verifier' "
        "if you visited the URL generated by this script).",
    )
    sys.exit(asyncio.run(main(parser.parse_args())))
