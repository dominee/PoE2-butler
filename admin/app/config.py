"""Admin configuration: credentials, IP allowlist, upstream URLs."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, SecretStr
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
    session_secret: SecretStr = SecretStr("admin-session-secret-change-me")
    session_cookie: str = "poe2b_admin"
    session_ttl_seconds: int = 60 * 60 * 4

    ip_allowlist: list[str] = Field(default_factory=list)

    database_url: str = "postgresql+asyncpg://poe2b:poe2b@postgres:5432/poe2b"
    redis_url: str = "redis://redis:6379/0"
    backend_base_url: str = "http://backend:8000"


@lru_cache
def get_admin_settings() -> AdminSettings:
    return AdminSettings()
