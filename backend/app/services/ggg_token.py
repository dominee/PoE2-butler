"""Refresh stored GGG OAuth tokens when access is expired or the API returns 401."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.ggg import GGGClient, GGGError
from app.db.models import User, UserToken
from app.security.crypto import TokenCipher

# Refresh a bit before mock/real access expiry to avoid 401 on the wire.
_REFRESH_MARGIN = timedelta(minutes=2)


def _at_utc(dt: datetime) -> datetime:
    """Tests/SQLite may return naive ``expires_at``; treat as UTC for comparison."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


def _should_refresh_proactively(tokens: UserToken, now: datetime) -> bool:
    if not tokens.refresh_token_enc or not tokens.expires_at:
        return False
    return _at_utc(tokens.expires_at) <= now + _REFRESH_MARGIN


async def _apply_refresh(
    session: AsyncSession,
    ggg: GGGClient,
    cipher: TokenCipher,
    user_tokens: UserToken,
) -> str:
    if not user_tokens.refresh_token_enc:
        raise GGGError(401, "no_refresh_token")
    rt = cipher.decrypt_str(user_tokens.refresh_token_enc)
    tr = await ggg.refresh_token(rt)
    user_tokens.access_token_enc = cipher.encrypt_str(tr.access_token)
    if tr.refresh_token:
        user_tokens.refresh_token_enc = cipher.encrypt_str(tr.refresh_token)
    user_tokens.expires_at = (
        datetime.now(UTC) + timedelta(seconds=tr.expires_in) if tr.expires_in else None
    )
    if tr.scope:
        user_tokens.scope = tr.scope
    return tr.access_token


async def get_valid_ggg_access(
    session: AsyncSession, user: User, ggg: GGGClient, cipher: TokenCipher
) -> str:
    """Return a usable access token, refreshing with the refresh token if near expiry."""
    user_tokens = await session.get(UserToken, user.id)
    if user_tokens is None:
        raise RuntimeError("user_has_no_tokens")
    now = datetime.now(UTC)
    if _should_refresh_proactively(user_tokens, now):
        return await _apply_refresh(session, ggg, cipher, user_tokens)
    return cipher.decrypt_str(user_tokens.access_token_enc)


async def force_refresh_ggg_access(
    session: AsyncSession, user: User, ggg: GGGClient, cipher: TokenCipher
) -> str:
    """Force a token refresh (e.g. after a 401 from the GGG API)."""
    user_tokens = await session.get(UserToken, user.id)
    if user_tokens is None:
        raise RuntimeError("user_has_no_tokens")
    return await _apply_refresh(session, ggg, cipher, user_tokens)
