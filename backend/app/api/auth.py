"""OAuth2 authorization endpoints: login, callback, logout."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Cookie, Depends, HTTPException, Query, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.ggg import GGGClient, GGGError
from app.config import Settings, get_settings
from app.db.base import get_session, _session_factory
from app.db.models import User, UserToken
from app.deps import (
    get_cipher,
    get_ggg_client,
    get_pending_auth_store,
    get_session_store,
)
from app.logging import get_logger
from app.security.crypto import TokenCipher
from app.security.pkce import (
    code_challenge_s256,
    generate_code_verifier,
    generate_state,
)
from app.security.sessions import PendingAuth, PendingAuthStore, SessionStore
from app.services.snapshot import refresh_user_snapshot

log = get_logger("app.api.auth")

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _set_session_cookie(response: Response, settings: Settings, sid: str, csrf: str) -> None:
    response.set_cookie(
        key=settings.session_cookie_name,
        value=sid,
        max_age=settings.session_ttl_seconds,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )
    # CSRF cookie: readable from JS so the SPA can echo it in X-CSRF-Token.
    response.set_cookie(
        key=settings.csrf_cookie_name,
        value=csrf,
        max_age=settings.session_ttl_seconds,
        httponly=False,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )


def _clear_session_cookie(response: Response, settings: Settings) -> None:
    for name in (settings.session_cookie_name, settings.csrf_cookie_name):
        response.delete_cookie(name, path="/")


@router.get("/login", summary="Begin OAuth2 login")
async def login(
    settings: Settings = Depends(get_settings),
    ggg: GGGClient = Depends(get_ggg_client),
    pending_store: PendingAuthStore = Depends(get_pending_auth_store),
) -> RedirectResponse:
    verifier = generate_code_verifier()
    state = generate_state()
    await pending_store.put(
        state,
        PendingAuth(verifier=verifier, redirect_after=f"{settings.app_base_url}/app"),
    )
    url = ggg.authorize_url(state=state, code_challenge=code_challenge_s256(verifier))
    return RedirectResponse(url, status_code=status.HTTP_302_FOUND)


@router.get("/callback", summary="OAuth2 callback")
async def callback(
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    settings: Settings = Depends(get_settings),
    ggg: GGGClient = Depends(get_ggg_client),
    pending_store: PendingAuthStore = Depends(get_pending_auth_store),
    sessions: SessionStore = Depends(get_session_store),
    db: AsyncSession = Depends(get_session),
    cipher: TokenCipher = Depends(get_cipher),
) -> RedirectResponse:
    if not code or not state:
        raise HTTPException(status_code=400, detail="missing_code_or_state")

    pending = await pending_store.consume(state)
    if pending is None:
        raise HTTPException(status_code=400, detail="invalid_or_expired_state")

    try:
        tokens = await ggg.exchange_code(code=code, code_verifier=pending.verifier)
    except GGGError as exc:
        log.warning("auth.exchange_failed", status=exc.status_code)
        raise HTTPException(status_code=400, detail="oauth_exchange_failed") from exc

    try:
        profile = await ggg.get_profile(tokens.access_token)
    except GGGError as exc:
        log.warning("auth.profile_failed", status=exc.status_code)
        raise HTTPException(status_code=400, detail="oauth_profile_failed") from exc

    account_name = profile.get("name") or ""
    if not account_name:
        raise HTTPException(status_code=400, detail="missing_account_name")

    # Upsert user row.
    existing = await db.execute(select(User).where(User.ggg_account_name == account_name))
    user = existing.scalar_one_or_none()
    if user is None:
        user = User(
            id=uuid.uuid4(),
            ggg_account_name=account_name,
            ggg_uuid=profile.get("uuid"),
            realm=profile.get("realm", "pc"),
        )
        db.add(user)
        await db.flush()

    user.last_login_at = datetime.now(UTC)

    expires_at = (
        datetime.now(UTC) + timedelta(seconds=tokens.expires_in) if tokens.expires_in else None
    )
    user_tokens = await db.get(UserToken, user.id)
    access_enc = cipher.encrypt_str(tokens.access_token)
    refresh_enc = cipher.encrypt_str(tokens.refresh_token) if tokens.refresh_token else None
    if user_tokens is None:
        db.add(
            UserToken(
                user_id=user.id,
                access_token_enc=access_enc,
                refresh_token_enc=refresh_enc,
                scope=tokens.scope,
                expires_at=expires_at,
            )
        )
    else:
        user_tokens.access_token_enc = access_enc
        if refresh_enc is not None:
            user_tokens.refresh_token_enc = refresh_enc
        user_tokens.scope = tokens.scope
        user_tokens.expires_at = expires_at

    await db.commit()

    # Snapshot refresh runs in its own transaction so that a GGG API hiccup or
    # a per-snapshot DB error never rolls back the user/token upsert above.
    # We merge `user` into the new session so that last_refreshed_at is saved.
    async with _session_factory()() as snap_db:
        snap_user = await snap_db.merge(user)
        await refresh_user_snapshot(session=snap_db, user=snap_user, ggg=ggg, cipher=cipher)
        await snap_db.commit()

    # Reload user so preferred_league written by refresh_user_snapshot is visible
    # (it lives in snap_db which is a separate SQLAlchemy session).
    await db.refresh(user)

    sid, data = await sessions.create(user_id=str(user.id), league=user.preferred_league)

    response = RedirectResponse(
        pending.redirect_after or settings.app_base_url,
        status_code=status.HTTP_302_FOUND,
    )
    _set_session_cookie(response, settings, sid, data.csrf)
    return response


@router.post("/logout", summary="Logout and revoke session")
async def logout(
    response: Response,
    settings: Settings = Depends(get_settings),
    sid: str | None = Cookie(default=None, alias="poe2b_session"),
    sessions: SessionStore = Depends(get_session_store),
    ggg: GGGClient = Depends(get_ggg_client),
    db: AsyncSession = Depends(get_session),
    cipher: TokenCipher = Depends(get_cipher),
) -> dict[str, str]:
    if sid:
        data = await sessions.get(sid)
        if data is not None:
            tokens = await db.get(UserToken, uuid.UUID(data.user_id))
            if tokens is not None and tokens.refresh_token_enc:
                try:
                    rt = cipher.decrypt_str(tokens.refresh_token_enc)
                    await ggg.revoke(rt)
                except Exception as exc:  # noqa: BLE001  best-effort
                    log.warning("auth.revoke_failed", error=str(exc))
        await sessions.destroy(sid)

    _clear_session_cookie(response, settings)
    return {"status": "logged_out"}
