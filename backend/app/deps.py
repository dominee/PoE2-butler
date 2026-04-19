"""FastAPI dependency providers: redis, ggg client, session store, current user."""

from __future__ import annotations

from collections.abc import AsyncIterator
from functools import lru_cache

from fastapi import Cookie, Depends, Header, HTTPException, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.ggg import GGGClient
from app.config import Settings, get_settings
from app.db.base import get_session
from app.db.models import User
from app.logging import get_logger
from app.security.crypto import TokenCipher
from app.security.csrf import tokens_equal
from app.security.sessions import (
    PendingAuthStore,
    RefreshCooldown,
    SessionData,
    SessionStore,
)
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
