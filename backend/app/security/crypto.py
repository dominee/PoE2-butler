"""Authenticated encryption for sensitive blobs (GGG tokens).

AES-GCM with a random 96-bit nonce per message.  The nonce is prepended to the
ciphertext and authentication tag.  The key is a 32-byte value pulled from the
``APP_SECRET_KEY`` setting (base64 encoded in env).
"""

from __future__ import annotations

import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.config import Settings

_NONCE_LEN = 12


def _derive_key(settings: Settings) -> bytes:
    raw = settings.app_secret_key.get_secret_value().encode("utf-8")
    try:
        key = base64.b64decode(raw, validate=True)
    except Exception:  # noqa: BLE001 - fall through to padding path
        key = raw
    if len(key) == 32:
        return key
    # Pad / truncate deterministically so dev defaults still work, but emit a
    # loud warning because this is not a real 32-byte key.
    from app.logging import get_logger

    get_logger("app.security.crypto").warning(
        "app_secret_key.not_32_bytes",
        length=len(key),
        hint="Set APP_SECRET_KEY to a base64-encoded 32-byte value in production.",
    )
    return (key + b"\0" * 32)[:32]


class TokenCipher:
    """Encrypts and decrypts arbitrary bytes with AES-GCM."""

    def __init__(self, settings: Settings) -> None:
        self._key = _derive_key(settings)
        self._aead = AESGCM(self._key)

    def encrypt(self, plaintext: bytes, *, associated_data: bytes | None = None) -> bytes:
        nonce = os.urandom(_NONCE_LEN)
        ct = self._aead.encrypt(nonce, plaintext, associated_data)
        return nonce + ct

    def decrypt(self, blob: bytes, *, associated_data: bytes | None = None) -> bytes:
        if len(blob) < _NONCE_LEN + 16:
            raise ValueError("ciphertext_too_short")
        nonce, ct = blob[:_NONCE_LEN], blob[_NONCE_LEN:]
        return self._aead.decrypt(nonce, ct, associated_data)

    def encrypt_str(self, plaintext: str, *, associated_data: bytes | None = None) -> bytes:
        return self.encrypt(plaintext.encode("utf-8"), associated_data=associated_data)

    def decrypt_str(self, blob: bytes, *, associated_data: bytes | None = None) -> str:
        return self.decrypt(blob, associated_data=associated_data).decode("utf-8")
