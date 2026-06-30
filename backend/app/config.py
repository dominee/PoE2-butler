"""Application configuration via pydantic-settings (12-factor)."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import AliasChoices, Field, SecretStr
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
    # PoE2 realm for live GGG character endpoints: GET /character/poe2[/{name}].
    # Leave empty for mock-ggg (legacy /account/characters paths).
    ggg_api_realm: str = ""
    # Fallback league when account:leagues scope is unavailable and inference fails.
    ggg_default_league: str = ""
    # Only scopes granted by GGG for PoE2. account:stashes is PoE1-only and not
    # yet available for PoE2. account:leagues was not granted — preferred league is
    # inferred from the character list (each character carries a "league" field).
    ggg_scopes: str = "account:profile account:characters"
    app_version: str = "0.1.0"
    ggg_user_agent_contact: str = "dev@hell.sk"
    ggg_user_agent_suffix: str = "PoE2-Hideout-Butler"
    # httpx read timeout for GGG (and dev mock) HTTP calls; raise for slow mock Poe.ninja scrapes.
    ggg_http_timeout_seconds: float = 15.0

    refresh_cooldown_seconds: int = 60
    # Max historic character gear snapshots retained per character (timeline UI).
    character_snapshot_history_max: int = 20
    default_trade_tolerance_pct: int = 10

    pricing_source: Literal["static", "poe_ninja"] = "static"
    # PoE1 mirrors use ``…/api/data`` + ``currencyoverview``; PoE2 live economy uses
    # ``https://poe.ninja`` + ``/poe2/api/economy/exchange/current/overview`` (see PoeNinjaSource).
    pricing_base_url: str = "https://poe.ninja"
    default_valuable_threshold_chaos: int = 100
    # Hybrid trade-based estimates (see docs/pricing_estimates.md)
    pricing_trade_estimate_enabled: bool = True
    pricing_scout_base_url: str = ""
    pricing_min_trade_listings: int = 5
    # Cap for ``POST /api/pricing/apprise`` stash backfill (missing DB rows first, then oldest).
    pricing_backfill_max_items: int = 40
    # Max concurrent hybrid price estimates (GGG trade2) across all arq workers.
    pricing_max_concurrent_estimates: int = 1
    # Arq worker: max jobs running at once (keep low; price estimates also gated by slot semaphore).
    arq_max_jobs: int = 2
    # Arq default job timeout is 300s; most jobs should finish well under this cap.
    arq_job_timeout_seconds: int = 7200
    # ``backfill_item_price_estimates`` runs many hybrid estimates; GGG 429 backoff (minutes) per
    # item makes wall time unbounded in the worst case — use a separate arq per-function timeout.
    arq_backfill_job_timeout_seconds: int = 172800
    # Minimum spacing between *successful* GGG trade2 API calls (search POST, list GET, fetch).
    # Honour GGG rate limits: keep this conservative (10s+ in prod).
    ggg_trade_min_interval_sec: float = Field(
        default=12.0,
        validation_alias=AliasChoices(
            "ggg_trade_min_interval_sec",
            "ggg_trade_fetch_min_interval_sec",
        ),
    )
    # Added on top of min_interval for the global trade2 lock after each HTTP 200.
    ggg_trade_extra_spacing_sec: float = 5.0
    ggg_trade_429_buffer_sec: int = 15
    ggg_trade_429_fallback_sec: int = 300
    ggg_trade_429_max_wait_sec: int = 600
    # Fallback when poe.ninja is not the active source (rough conversion to chaos)
    trade_listing_divine_to_chaos: float = 250.0
    trade_listing_exalt_to_chaos: float = 8.0

    # PoE2 trade site public filter metadata (optional; used by trade_stat_catalog).
    trade_filter_data_url: str = "https://www.pathofexile.com/api/trade2/data/filters"
    # Stat text → id catalogue for trade search filters (see trade_stat_index).
    trade_stats_data_url: str = "https://www.pathofexile.com/api/trade2/data/stats"
    # Base URL for POSTing a search; path is ``/{league}`` (league URL-encoded).
    trade_search_api_base: str = "https://www.pathofexile.com/api/trade2/search"

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
