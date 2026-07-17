"""API key generation and verification for machine access (Discord bot, etc.).

Key format: ``hob_<prefix12>_<secret32>``

- ``hob_`` — fixed discriminator, makes keys identifiable in logs / pastes.
- ``prefix12`` — 12 URL-safe characters stored **plaintext** in the DB for O(1) lookup.
- ``secret32`` — 32 URL-safe random characters; never stored, only its HMAC-SHA256 digest.

The hash stored in the DB is ``HMAC-SHA256(full_key, pepper)`` where ``pepper`` is derived
from the application secret key.  Constant-time comparison prevents timing attacks.
"""

from __future__ import annotations

import hmac
import secrets
from hashlib import sha256

_PREFIX_LEN = 12
_SECRET_LEN = 32
_KEY_DISCRIMINATOR = "hob"


def _pepper(app_secret: str) -> bytes:
    """Derive a stable 32-byte pepper from the application secret key."""
    return sha256(f"api_key_pepper:{app_secret}".encode()).digest()


def generate_api_key(app_secret: str) -> tuple[str, str, str]:
    """Return ``(full_key, prefix, key_hash)``.

    ``full_key`` is shown to the user **once** and never stored.
    ``prefix`` and ``key_hash`` are persisted in ``user_api_keys``.
    """
    prefix = secrets.token_urlsafe(_PREFIX_LEN)[:_PREFIX_LEN]
    secret = secrets.token_urlsafe(_SECRET_LEN)[:_SECRET_LEN]
    full_key = f"{_KEY_DISCRIMINATOR}_{prefix}_{secret}"
    key_hash = _compute_hash(full_key, app_secret)
    return full_key, prefix, key_hash


def verify_api_key(full_key: str, stored_hash: str, app_secret: str) -> bool:
    """Return True iff ``full_key`` hashes to ``stored_hash`` (constant-time)."""
    expected = _compute_hash(full_key, app_secret)
    return hmac.compare_digest(expected, stored_hash)


def extract_prefix(full_key: str) -> str | None:
    """Parse the 12-char prefix from a full key string.  Returns None if malformed."""
    parts = full_key.split("_", 2)
    if len(parts) != 3 or parts[0] != _KEY_DISCRIMINATOR:
        return None
    prefix = parts[1]
    if len(prefix) != _PREFIX_LEN:
        return None
    return prefix


def _compute_hash(full_key: str, app_secret: str) -> str:
    pepper = _pepper(app_secret)
    return hmac.new(pepper, full_key.encode(), sha256).hexdigest()
