"""Admin configuration: credentials, IP allowlist, upstream URLs."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AdminSettings(BaseSettings):
    """12-factor configuration for the observability console."""

    model_config = SettingsConfigDict(env_prefix="ADMIN_", extra="ignore")

    environment: str = "dev"
    log_level: str = "INFO"

    username: str = "admin"
    # Must be provided via env (ADMIN_PASSWORD_HASH). Keep default intentionally
    # non-sensitive to avoid committing a reusable hash to source control.
    password_hash: SecretStr = SecretStr(
        "CHANGE_ME"
    )
    totp_secret: SecretStr | None = None

    @field_validator("password_hash", mode="before")
    @classmethod
    def _normalize_password_hash(cls, v: object) -> object:
        """Strip accidental shell quotes; collapse ``$$`` from compose .env (``env_file``)."""
        if v is None or not isinstance(v, str):
            return v
        s = v.strip().strip("'\"")
        while "$$" in s:
            s = s.replace("$$", "$")
        return s

    @field_validator("totp_secret", mode="before")
    @classmethod
    def _empty_totp_means_disabled(cls, v: object) -> object:
        """Compose / .env often set ``ADMIN_TOTP_SECRET=``; treat as unset (no 2FA)."""
        if v is None:
            return None
        if isinstance(v, str) and not v.strip():
            return None
        return v
    session_secret: SecretStr = SecretStr("admin-session-secret-change-me")
    session_cookie: str = "poe2b_admin"
    session_ttl_seconds: int = 60 * 60 * 4

    ip_allowlist: list[str] = Field(default_factory=list)

    database_url: str = "postgresql+asyncpg://poe2b:poe2b@postgres:5432/poe2b"
    redis_url: str = "redis://redis:6379/0"
    backend_base_url: str = "http://backend:8000"
    internal_secret: SecretStr = SecretStr("")

    # 0 = disabled. When > 0, Overview polls ``GET /admin/api/summary`` every N seconds.
    dashboard_refresh_sec: int = 0


@lru_cache
def get_admin_settings() -> AdminSettings:
    return AdminSettings()
