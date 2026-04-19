"""PKCE and CSRF-like state helpers for the OAuth2 authorization code flow."""

from __future__ import annotations

import base64
import hashlib
import secrets


def _b64url_nopad(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def generate_code_verifier() -> str:
    """48 random bytes -> 64-char base64url PKCE verifier."""
    return _b64url_nopad(secrets.token_bytes(48))


def code_challenge_s256(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return _b64url_nopad(digest)


def generate_state() -> str:
    """128-bit random state token."""
    return _b64url_nopad(secrets.token_bytes(16))
