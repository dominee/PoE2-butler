"""Admin FastAPI app: session auth + server-side HTML observability views."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

from fastapi import Cookie, Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from admin.app.auth import AdminSession, AuthError, SessionManager
from admin.app.config import AdminSettings, get_admin_settings
from admin.app.dashboard_data import bundle_for_json, load_dashboard_bundle
from admin.app.db import enrich_price_queue_rows, list_users, recent_snapshots
from admin.app.middleware import AdminSecurityHeaders, IPAllowlistMiddleware
from admin.app.redis_stats import (
    backend_health,
    probe_ok,
    top_queued_price_estimate_jobs,
)

TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
_STATIC_DIR = Path(__file__).parent / "static"


def _jinja_tojson(v: object) -> str:
    return json.dumps(v, ensure_ascii=True, default=str, separators=(",", ":"))


TEMPLATES.env.filters["tojson"] = _jinja_tojson


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

    if _STATIC_DIR.is_dir():
        app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

    _register_routes(app)
    return app


def _register_routes(app: FastAPI) -> None:

    @app.get("/")
    async def root() -> RedirectResponse:
        """Dedicated admin host has no SPA at `/`; send browsers to the console."""
        return RedirectResponse(url="/admin/", status_code=302)

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
            secure=get_admin_settings().environment in ("prod", "uat"),
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

    @app.get("/admin/api/summary")
    async def api_summary(_session: AdminSession = Depends(_require_session)) -> JSONResponse:
        bundle = await load_dashboard_bundle()
        return JSONResponse(bundle_for_json(bundle))

    @app.get("/admin/", response_class=HTMLResponse)
    async def home(
        request: Request,
        session: AdminSession = Depends(_require_session),
    ) -> HTMLResponse:
        settings = get_admin_settings()
        bundle = await load_dashboard_bundle()
        context = {
            "session": session,
            "active": "home",
            "dashboard_refresh_sec": settings.dashboard_refresh_sec,
            **bundle,
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
        bundle = await load_dashboard_bundle()
        return TEMPLATES.TemplateResponse(
            request,
            "cache.html",
            {
                "session": session,
                "active": "cache",
                "redis": bundle["redis"],
                "price_cache": bundle["price_cache"],
                "queue": bundle["queue"],
                "price_estimates": bundle.get("price_estimates") or {},
                "arq_jobs": bundle.get("arq_jobs") or {},
            },
        )

    @app.get("/admin/price-queue", response_class=HTMLResponse)
    async def price_queue(
        request: Request,
        session: AdminSession = Depends(_require_session),
    ) -> HTMLResponse:
        rows = await top_queued_price_estimate_jobs(limit=50)
        await enrich_price_queue_rows(rows)
        return TEMPLATES.TemplateResponse(
            request,
            "price_queue.html",
            {"session": session, "active": "price_queue", "rows": rows},
        )

    @app.get("/admin/upstream", response_class=HTMLResponse)
    async def upstream(
        request: Request,
        session: AdminSession = Depends(_require_session),
    ) -> HTMLResponse:
        health = await backend_health()
        upstream_ok = all(probe_ok(v) for v in health.values()) if health else False
        return TEMPLATES.TemplateResponse(
            request,
            "upstream.html",
            {
                "session": session,
                "active": "upstream",
                "health": health,
                "upstream_ok": upstream_ok,
            },
        )


app = create_app()
