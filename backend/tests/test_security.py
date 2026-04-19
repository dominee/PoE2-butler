"""Unit tests for security primitives: crypto, PKCE."""

from __future__ import annotations

import base64

from app.config import Settings
from app.security.crypto import TokenCipher
from app.security.pkce import (
    code_challenge_s256,
    generate_code_verifier,
    generate_state,
)


def _settings_with_key(key: bytes) -> Settings:
    from pydantic import SecretStr

    return Settings(app_secret_key=SecretStr(base64.b64encode(key).decode("ascii")))


def test_cipher_roundtrip_binary() -> None:
    cipher = TokenCipher(_settings_with_key(b"0" * 32))
    plaintext = b"super secret access token"
    blob = cipher.encrypt(plaintext)
    assert blob != plaintext
    assert cipher.decrypt(blob) == plaintext


def test_cipher_roundtrip_str() -> None:
    cipher = TokenCipher(_settings_with_key(b"A" * 32))
    blob = cipher.encrypt_str("hello world")
    assert cipher.decrypt_str(blob) == "hello world"


def test_cipher_aead_associated_data_mismatch_fails() -> None:
    import pytest
    from cryptography.exceptions import InvalidTag

    cipher = TokenCipher(_settings_with_key(b"B" * 32))
    blob = cipher.encrypt(b"payload", associated_data=b"user-1")
    with pytest.raises(InvalidTag):
        cipher.decrypt(blob, associated_data=b"user-2")


def test_pkce_verifier_and_challenge() -> None:
    verifier = generate_code_verifier()
    assert len(verifier) >= 43
    challenge = code_challenge_s256(verifier)
    assert challenge and "=" not in challenge
    assert len(challenge) >= 43
    # Same verifier -> same challenge.
    assert code_challenge_s256(verifier) == challenge


def test_state_is_urlsafe_and_long_enough() -> None:
    state = generate_state()
    assert len(state) >= 20
    assert "=" not in state
