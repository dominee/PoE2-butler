"""CSRF verification for admin POST forms."""

from __future__ import annotations

from admin.app.config import AdminSettings
from admin.app.csrf import issue_csrf_token, verify_csrf_token


def test_csrf_issue_and_verify() -> None:
    secret = "unit-test-secret"
    token = issue_csrf_token(secret)
    assert verify_csrf_token(secret, token) is True
    assert verify_csrf_token(secret, token + "x") is False
    assert verify_csrf_token(secret, "bad.token") is False
