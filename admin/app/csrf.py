"""CSRF tokens for admin form POSTs (double-submit via session cookie)."""

from __future__ import annotations

import hmac
import secrets
from hashlib import sha256

_CSRF_COOKIE = "poe2b_admin_csrf"


def issue_csrf_token(session_secret: str) -> str:
    raw = secrets.token_urlsafe(32)
    sig = hmac.new(session_secret.encode("utf-8"), raw.encode("utf-8"), sha256).hexdigest()
    return f"{raw}.{sig}"


def verify_csrf_token(session_secret: str, token: str | None) -> bool:
    if not token or "." not in token:
        return False
    raw, sig = token.rsplit(".", 1)
    expected = hmac.new(session_secret.encode("utf-8"), raw.encode("utf-8"), sha256).hexdigest()
    return hmac.compare_digest(expected, sig)


def csrf_cookie_name() -> str:
    return _CSRF_COOKIE
