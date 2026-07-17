"""FastAPI dependency providers: redis, ggg client, session store, current user."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from functools import lru_cache

from fastapi import Cookie, Depends, Header, HTTPException, status
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.ggg import GGGClient
from app.config import Settings, get_settings
from app.db.base import get_session
from app.db.models import User, UserApiKey
from app.logging import get_logger
from app.security.api_keys import extract_prefix, verify_api_key
from app.security.crypto import TokenCipher
from app.security.csrf import tokens_equal
from app.security.sessions import (
    PendingAuthStore,
    RefreshCooldown,
    SessionData,
    SessionStore,
)
from app.services import api_key_ratelimit as _api_key_ratelimit_mod
from app.services.pricing import PriceCache, PriceSource
from app.services.pricing.poe_ninja import PoeNinjaSource
from app.services.pricing.service import PricingService
from app.services.pricing.static import StaticPriceSource

log = get_logger("app.deps")


@lru_cache
def _redis_singleton() -> Redis:
    return Redis.from_url(get_settings().redis_url, decode_responses=True)


async def get_redis() -> AsyncIterator[Redis]:
    yield _redis_singleton()


@lru_cache
def _cipher_singleton() -> TokenCipher:
    return TokenCipher(get_settings())


def get_cipher() -> TokenCipher:
    return _cipher_singleton()


async def get_ggg_client() -> AsyncIterator[GGGClient]:
    client = GGGClient(get_settings())
    try:
        yield client
    finally:
        await client.aclose()


def get_session_store(redis: Redis = Depends(get_redis)) -> SessionStore:
    return SessionStore(redis, ttl_seconds=get_settings().session_ttl_seconds)


def get_pending_auth_store(redis: Redis = Depends(get_redis)) -> PendingAuthStore:
    return PendingAuthStore(redis)


def get_refresh_cooldown(redis: Redis = Depends(get_redis)) -> RefreshCooldown:
    settings = get_settings()
    return RefreshCooldown(redis, settings.refresh_cooldown_seconds)


async def get_session_data(
    settings: Settings = Depends(get_settings),
    sid: str | None = Cookie(default=None, alias="poe2b_session"),
    store: SessionStore = Depends(get_session_store),
) -> SessionData:
    if not sid:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="no_session")
    data = await store.get(sid)
    if data is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_session")
    # Unused param silences linter about unused settings; keeps signature stable.
    _ = settings
    return data


async def get_current_user(
    data: SessionData = Depends(get_session_data),
    db: AsyncSession = Depends(get_session),
) -> User:
    import uuid

    user = await db.get(User, uuid.UUID(data.user_id))
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="user_not_found")
    return user


@lru_cache
def _price_source_singleton() -> PriceSource:
    settings = get_settings()
    if settings.pricing_source == "poe_ninja":
        return PoeNinjaSource(settings.pricing_base_url)
    return StaticPriceSource()


def get_price_source() -> PriceSource:
    return _price_source_singleton()


def get_price_cache(redis: Redis = Depends(get_redis)) -> PriceCache:
    return PriceCache(redis)


def get_pricing_service(
    source: PriceSource = Depends(get_price_source),
    cache: PriceCache = Depends(get_price_cache),
) -> PricingService:
    return PricingService(source, cache)


def require_csrf(
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
    data: SessionData = Depends(get_session_data),
) -> None:
    if not tokens_equal(x_csrf_token or "", data.csrf):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="csrf_failed")


async def _resolve_api_key(
    token: str,
    db: AsyncSession,
    redis: Redis,
    settings: Settings,
) -> User:
    """Validate a raw API key token and return the owning User.

    Raises HTTP 401 on any validation failure so callers never learn which step failed.
    Updates ``last_used_at`` on success and enforces the per-key rate limit.
    """
    prefix = extract_prefix(token)
    if not prefix:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_api_key")

    result = await db.execute(
        select(UserApiKey).where(
            UserApiKey.key_prefix == prefix,
            UserApiKey.revoked_at.is_(None),
        )
    )
    key_row = result.scalar_one_or_none()
    if key_row is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_api_key")

    app_secret = settings.app_secret_key.get_secret_value()
    if not verify_api_key(token, key_row.key_hash, app_secret):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_api_key")

    await _api_key_ratelimit_mod.enforce_api_key_rate_limit(
        redis, prefix, settings.api_key_rate_limit_per_minute
    )

    key_row.last_used_at = datetime.now(UTC)
    await db.commit()

    user = await db.get(User, key_row.user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="user_not_found")
    return user


async def get_api_key_user(
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
    settings: Settings = Depends(get_settings),
) -> User:
    """Authenticate via ``Authorization: Bearer hob_…`` API key only."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="api_key_required")
    token = authorization[len("Bearer "):]
    return await _resolve_api_key(token, db, redis, settings)


async def get_current_user_any(
    sid: str | None = Cookie(default=None, alias="poe2b_session"),
    authorization: str | None = Header(default=None),
    store: SessionStore = Depends(get_session_store),
    db: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
    settings: Settings = Depends(get_settings),
) -> User:
    """Accept either a session cookie **or** a Bearer API key.

    Session cookie takes precedence so browser clients are unaffected.
    Raises HTTP 401 when neither credential is valid.
    """
    if sid:
        data = await store.get(sid)
        if data is not None:
            user = await db.get(User, uuid.UUID(data.user_id))
            if user is not None:
                return user

    if authorization and authorization.startswith("Bearer "):
        token = authorization[len("Bearer "):]
        return await _resolve_api_key(token, db, redis, settings)

    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="no_auth")


async def get_current_user_mutate(
    sid: str | None = Cookie(default=None, alias="poe2b_session"),
    authorization: str | None = Header(default=None),
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
    store: SessionStore = Depends(get_session_store),
    db: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
    settings: Settings = Depends(get_settings),
) -> User:
    """Accept Bearer API key (no CSRF) **or** session cookie + CSRF for mutations.

    API key callers skip CSRF entirely — they are machine clients without a browser session.
    Session callers must supply a valid X-CSRF-Token header.
    """
    if authorization and authorization.startswith("Bearer "):
        token = authorization[len("Bearer "):]
        return await _resolve_api_key(token, db, redis, settings)

    if not sid:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="no_session")
    data = await store.get(sid)
    if data is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_session")
    if not tokens_equal(x_csrf_token or "", data.csrf):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="csrf_failed")
    user = await db.get(User, uuid.UUID(data.user_id))
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="user_not_found")
    return user
