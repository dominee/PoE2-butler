"""Session-backed authentication with optional TOTP second factor."""

from __future__ import annotations

import secrets
import time
from dataclasses import dataclass

import bcrypt
import pyotp
from itsdangerous import BadSignature, TimestampSigner

from admin.app.config import AdminSettings


@dataclass
class AdminSession:
    username: str
    issued_at: float
    nonce: str


class AuthError(Exception):
    """Raised when credentials / TOTP are wrong."""


class SessionManager:
    def __init__(self, settings: AdminSettings) -> None:
        self._settings = settings
        self._signer = TimestampSigner(settings.session_secret.get_secret_value())

    def verify_password(self, username: str, password: str) -> bool:
        if not secrets.compare_digest(username, self._settings.username):
            return False
        stored = self._settings.password_hash.get_secret_value().encode()
        # bcrypt caps inputs at 72 bytes; keep behaviour consistent across clients.
        candidate = password.encode()[:72]
        try:
            return bcrypt.checkpw(candidate, stored)
        except ValueError:
            return False

    def verify_totp(self, code: str) -> bool:
        if self._settings.totp_secret is None:
            return True  # TOTP disabled
        secret = self._settings.totp_secret.get_secret_value()
        totp = pyotp.TOTP(secret)
        return totp.verify(code.strip(), valid_window=1)

    def requires_totp(self) -> bool:
        return self._settings.totp_secret is not None

    def issue(self, username: str) -> str:
        payload = f"{username}|{int(time.time())}|{secrets.token_urlsafe(8)}"
        return self._signer.sign(payload.encode()).decode()

    def validate(self, token: str | None) -> AdminSession | None:
        if not token:
            return None
        try:
            raw = self._signer.unsign(
                token.encode(), max_age=self._settings.session_ttl_seconds
            ).decode()
        except BadSignature:
            return None
        try:
            username, issued_s, nonce = raw.split("|", 2)
        except ValueError:
            return None
        if username != self._settings.username:
            return None
        return AdminSession(username=username, issued_at=float(issued_s), nonce=nonce)
