"""Admin FastAPI app: session auth + server-side HTML observability views."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import Cookie, Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy import text

from admin.app.auth import AdminSession, AuthError, SessionManager
from admin.app.config import AdminSettings, get_admin_settings
from admin.app.db import (
    count_snapshots_by_kind,
    get_engine,
    list_users,
    recent_snapshots,
)
from admin.app.middleware import AdminSecurityHeaders, IPAllowlistMiddleware
from admin.app.redis_stats import (
    backend_health,
    price_cache_summary,
    queue_summary,
    redis_summary,
)

TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


def _session_manager() -> SessionManager:
    return SessionManager(get_admin_settings())


async def _require_session(
    request: Request,
    token: Annotated[str | None, Cookie(alias="poe2b_admin")] = None,
    settings: AdminSettings = Depends(get_admin_settings),
) -> AdminSession:
    mgr = SessionManager(settings)
    session = mgr.validate(token)
    if session is None:
        # We use an exception so FastAPI honours ``response_class`` on nested routes;
        # middleware would complicate per-route login-redirects.
        raise HTTPException(status_code=302, headers={"Location": "/admin/login"})
    request.state.session = session
    return session


def create_app() -> FastAPI:
    settings = get_admin_settings()
    app = FastAPI(title="PoE2 Butler Admin", docs_url=None, redoc_url=None)
    app.add_middleware(AdminSecurityHeaders)
    app.add_middleware(IPAllowlistMiddleware, allowlist=settings.ip_allowlist)

    _register_routes(app)
    return app


def _register_routes(app: FastAPI) -> None:

    @app.get("/admin/login", response_class=HTMLResponse)
    async def login_form(request: Request) -> HTMLResponse:
        mgr = _session_manager()
        return TEMPLATES.TemplateResponse(
            request,
            "login.html",
            {"requires_totp": mgr.requires_totp(), "error": None, "session": None},
        )

    @app.post("/admin/login")
    async def login_submit(
        request: Request,
        username: Annotated[str, Form()],
        password: Annotated[str, Form()],
        totp: Annotated[str | None, Form()] = None,
    ) -> Response:
        mgr = _session_manager()
        try:
            if not mgr.verify_password(username, password):
                raise AuthError("invalid credentials")
            if mgr.requires_totp() and not mgr.verify_totp(totp or ""):
                raise AuthError("invalid totp")
        except AuthError as exc:
            return TEMPLATES.TemplateResponse(
                request,
                "login.html",
                {
                    "requires_totp": mgr.requires_totp(),
                    "error": str(exc),
                    "session": None,
                },
                status_code=400,
            )
        token = mgr.issue(username)
        response = RedirectResponse(url="/admin/", status_code=303)
        response.set_cookie(
            get_admin_settings().session_cookie,
            token,
            httponly=True,
            samesite="strict",
            secure=get_admin_settings().environment == "prod",
            max_age=get_admin_settings().session_ttl_seconds,
        )
        return response

    @app.get("/admin/logout")
    async def logout() -> Response:
        response = RedirectResponse(url="/admin/login", status_code=303)
        response.delete_cookie(get_admin_settings().session_cookie)
        return response

    @app.get("/admin/healthz")
    async def healthz() -> dict:
        return {"status": "ok"}

    @app.get("/admin/", response_class=HTMLResponse)
    async def home(
        request: Request,
        session: AdminSession = Depends(_require_session),
    ) -> HTMLResponse:
        engine = get_engine()
        async with engine.connect() as conn:
            totals_rows = await conn.execute(
                text(
                    "SELECT (SELECT COUNT(*) FROM users) AS users, "
                    "(SELECT COUNT(*) FROM snapshots) AS snapshots"
                )
            )
            totals = dict(totals_rows.first()._mapping)
        context = {
            "session": session,
            "active": "home",
            "totals": totals,
            "snapshots_by_kind": await count_snapshots_by_kind(),
            "redis": await redis_summary(),
            "price_cache": await price_cache_summary(),
            "queue": await queue_summary(),
        }
        return TEMPLATES.TemplateResponse(request, "home.html", context)

    @app.get("/admin/users", response_class=HTMLResponse)
    async def users(
        request: Request,
        session: AdminSession = Depends(_require_session),
    ) -> HTMLResponse:
        return TEMPLATES.TemplateResponse(
            request,
            "users.html",
            {"session": session, "active": "users", "users": await list_users()},
        )

    @app.get("/admin/snapshots", response_class=HTMLResponse)
    async def snapshots(
        request: Request,
        session: AdminSession = Depends(_require_session),
    ) -> HTMLResponse:
        return TEMPLATES.TemplateResponse(
            request,
            "snapshots.html",
            {
                "session": session,
                "active": "snapshots",
                "snapshots": await recent_snapshots(),
            },
        )

    @app.get("/admin/cache", response_class=HTMLResponse)
    async def cache(
        request: Request,
        session: AdminSession = Depends(_require_session),
    ) -> HTMLResponse:
        return TEMPLATES.TemplateResponse(
            request,
            "cache.html",
            {
                "session": session,
                "active": "cache",
                "redis": await redis_summary(),
                "price_cache": await price_cache_summary(),
                "queue": await queue_summary(),
            },
        )

    @app.get("/admin/upstream", response_class=HTMLResponse)
    async def upstream(
        request: Request,
        session: AdminSession = Depends(_require_session),
    ) -> HTMLResponse:
        return TEMPLATES.TemplateResponse(
            request,
            "upstream.html",
            {
                "session": session,
                "active": "upstream",
                "health": await backend_health(),
            },
        )


app = create_app()
