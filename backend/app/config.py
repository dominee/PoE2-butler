"""Application configuration via pydantic-settings (12-factor)."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration pulled from environment variables.

    Every secret is a `SecretStr` so that it does not show up in
    `repr()` and structured log dumps.
    """

    model_config = SettingsConfigDict(
        env_file=None,
        env_prefix="",
        case_sensitive=False,
        extra="ignore",
    )

    environment: Literal["dev", "test", "prod", "uat"] = "dev"
    log_level: str = "INFO"
    public_domain: str = "localhost"
    app_base_url: str = "http://app.localhost"
    api_base_url: str = "http://api.localhost"

    app_secret_key: SecretStr = Field(
        default=SecretStr("dev-only-change-me-dev-only-change-me-dev-only="),
        description="32-byte base64 key used for AES-GCM encryption of GGG tokens.",
    )
    session_signing_key: SecretStr = Field(
        default=SecretStr("dev-only-sign-me-dev-only-sign-me-dev-only-sig="),
        description="32-byte base64 key used to sign session cookies.",
    )
    session_cookie_name: str = "poe2b_session"
    session_ttl_seconds: int = 14 * 24 * 60 * 60
    csrf_cookie_name: str = "poe2b_csrf"

    database_url: str = "postgresql+asyncpg://poe2b:poe2b@postgres:5432/poe2b"
    redis_url: str = "redis://redis:6379/0"

    ggg_oauth_base_url: str = "http://mock-ggg:9000"
    ggg_api_base_url: str = "http://mock-ggg:9000"
    # Browser-facing base URL used only in the /login redirect to the IdP's
    # authorize endpoint.  Defaults to ggg_oauth_base_url (correct for prod
    # where the IdP is publicly reachable), but must be overridden in dev to
    # the Traefik-routed hostname so the browser can actually reach mock-ggg.
    ggg_oauth_authorize_base_url: str = ""
    ggg_client_id: str = "poe2-butler-dev"
    ggg_client_secret: SecretStr = SecretStr("poe2-butler-dev-secret")
    ggg_redirect_uri: str = "http://api.localhost/api/auth/callback"
    ggg_scopes: str = "account:profile account:characters account:stashes account:leagues"
    app_version: str = "0.1.0"
    ggg_user_agent_contact: str = "dev@hell.sk"
    ggg_user_agent_suffix: str = "PoE2-Hideout-Butler"

    refresh_cooldown_seconds: int = 60
    default_trade_tolerance_pct: int = 10

    pricing_source: Literal["static", "poe_ninja"] = "static"
    pricing_base_url: str = "https://poe.ninja/api/data"
    default_valuable_threshold_chaos: int = 100

    cors_allow_origins: list[str] = Field(default_factory=lambda: ["http://app.localhost"])

    @property
    def is_prod(self) -> bool:
        return self.environment == "prod"

    @property
    def cookie_secure(self) -> bool:
        # UAT: public HTTPS behind Cloudflare (same as prod for browser cookies)
        return self.environment in ("prod", "uat")


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()
