"""Unit tests for the admin auth helpers."""

from __future__ import annotations

import bcrypt
import pyotp
import pytest
from pydantic import SecretStr

from admin.app.auth import SessionManager
from admin.app.config import AdminSettings


def _settings(totp: str | None = None) -> AdminSettings:
    hashed = bcrypt.hashpw(b"s3cret", bcrypt.gensalt()).decode()
    return AdminSettings(
        username="admin",
        password_hash=SecretStr(hashed),
        totp_secret=SecretStr(totp) if totp else None,
        session_secret=SecretStr("test-secret"),
    )


def test_password_verification_success() -> None:
    mgr = SessionManager(_settings())
    assert mgr.verify_password("admin", "s3cret") is True
    assert mgr.verify_password("admin", "wrong") is False
    assert mgr.verify_password("mallory", "s3cret") is False


def test_issue_and_validate_roundtrip() -> None:
    mgr = SessionManager(_settings())
    token = mgr.issue("admin")
    session = mgr.validate(token)
    assert session is not None
    assert session.username == "admin"


def test_tampered_token_is_rejected() -> None:
    mgr = SessionManager(_settings())
    token = mgr.issue("admin")
    payload, sep, signature = token.rpartition(".")
    assert sep == "."
    tampered_payload = payload[:-1] + ("x" if payload[-1] != "x" else "y")
    tampered = f"{tampered_payload}.{signature}"
    assert mgr.validate(tampered) is None


def test_totp_optional() -> None:
    mgr = SessionManager(_settings())
    assert mgr.requires_totp() is False
    assert mgr.verify_totp("anything") is True


def test_totp_enforced() -> None:
    secret = pyotp.random_base32()
    mgr = SessionManager(_settings(totp=secret))
    assert mgr.requires_totp() is True
    code = pyotp.TOTP(secret).now()
    assert mgr.verify_totp(code) is True
    assert mgr.verify_totp("000000") is False


@pytest.mark.parametrize("invalid", ["", "not-a-token", "totally bogus"])
def test_garbage_tokens_return_none(invalid: str) -> None:
    mgr = SessionManager(_settings())
    assert mgr.validate(invalid) is None
