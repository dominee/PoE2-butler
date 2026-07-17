"""Admin FastAPI app: session auth + server-side HTML observability views."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

from fastapi import Cookie, Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from admin.app.audit import audit_action
from admin.app.auth import AdminSession, AuthError, SessionManager
from admin.app.backend_client import post_admin_action
from admin.app.config import AdminSettings, get_admin_settings
from admin.app.csrf import csrf_cookie_name, issue_csrf_token, verify_csrf_token
from admin.app.dashboard_data import bundle_for_json, load_dashboard_bundle
from admin.app.db import (
    count_character_history,
    count_user_snapshots_by_kind,
    enrich_price_queue_rows,
    get_user_active_api_key,
    get_user_by_id,
    get_user_token_meta,
    list_user_price_estimates,
    list_user_shares,
    list_user_snapshots,
    list_users,
    recent_snapshots,
)
from admin.app.middleware import AdminSecurityHeaders, IPAllowlistMiddleware
from admin.app.redis_stats import (
    backend_health,
    clear_inflight_price_estimate_jobs,
    delete_price_job_key,
    probe_ok,
    top_queued_price_estimate_jobs,
)
from admin.app.redis_user import user_redis_state
from admin.app.user_dashboard_data import (
    load_user_dashboard_bundle,
    user_bundle_for_json,
    user_chart_payload,
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
    app = FastAPI(title="Hideout Butler Admin", docs_url=None, redoc_url=None)
    app.add_middleware(AdminSecurityHeaders)
    app.add_middleware(IPAllowlistMiddleware, allowlist=settings.ip_allowlist)

    if _STATIC_DIR.is_dir():
        app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

    _register_routes(app)
    return app


def _csrf_token_for_request(request: Request) -> str:
    return request.cookies.get(csrf_cookie_name(), "")


def _verify_csrf(request: Request, form_token: str | None) -> None:
    settings = get_admin_settings()
    cookie = _csrf_token_for_request(request)
    secret = settings.session_secret.get_secret_value()
    if not form_token or not cookie or form_token != cookie:
        raise HTTPException(status_code=403, detail="csrf_mismatch")
    if not verify_csrf_token(secret, form_token):
        raise HTTPException(status_code=403, detail="csrf_invalid")


def _attach_csrf_cookie(response: Response, settings: AdminSettings) -> None:
    token = issue_csrf_token(settings.session_secret.get_secret_value())
    response.set_cookie(
        csrf_cookie_name(),
        token,
        httponly=True,
        samesite="strict",
        secure=settings.environment in ("prod", "uat"),
        max_age=settings.session_ttl_seconds,
    )


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
        settings = get_admin_settings()
        response.set_cookie(
            get_admin_settings().session_cookie,
            token,
            httponly=True,
            samesite="strict",
            secure=get_admin_settings().environment in ("prod", "uat"),
            max_age=get_admin_settings().session_ttl_seconds,
        )
        _attach_csrf_cookie(response, settings)
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

    @app.get("/admin/api/users/stats")
    async def api_users_stats(
        _session: AdminSession = Depends(_require_session),
        days: int = 90,
    ) -> JSONResponse:
        bundle = await load_user_dashboard_bundle(days=days)
        return JSONResponse(user_bundle_for_json(bundle))

    @app.get("/admin/users", response_class=HTMLResponse)
    async def users(
        request: Request,
        session: AdminSession = Depends(_require_session),
        q: str | None = None,
        days: int = 90,
    ) -> HTMLResponse:
        user_stats = await load_user_dashboard_bundle(days=days)
        return TEMPLATES.TemplateResponse(
            request,
            "users.html",
            {
                "session": session,
                "active": "users",
                "users": await list_users(query=q),
                "q": q or "",
                "user_stats": user_stats,
                "chart_data_json": json.dumps(user_chart_payload(user_stats)),
            },
        )

    @app.get("/admin/users/{user_id}", response_class=HTMLResponse)
    async def user_detail(
        request: Request,
        user_id: str,
        session: AdminSession = Depends(_require_session),
    ) -> HTMLResponse:
        user = await get_user_by_id(user_id)
        if user is None:
            raise HTTPException(status_code=404, detail="user_not_found")
        notice = request.query_params.get("notice")
        token_meta = await get_user_token_meta(user_id)
        redis_state = await user_redis_state(user_id)
        api_key_meta = await get_user_active_api_key(user_id)
        return TEMPLATES.TemplateResponse(
            request,
            "user_detail.html",
            {
                "session": session,
                "active": "users",
                "user": user,
                "token": token_meta,
                "api_key": api_key_meta,
                "redis_state": redis_state,
                "snapshot_counts": await count_user_snapshots_by_kind(user_id),
                "snapshots": await list_user_snapshots(user_id),
                "estimates": await list_user_price_estimates(user_id),
                "shares": await list_user_shares(user_id),
                "history_count": await count_character_history(user_id),
                "ops_enabled": bool(
                    get_admin_settings().internal_secret.get_secret_value().strip()
                ),
                "notice": notice,
            },
        )

    @app.post("/admin/users/{user_id}/refresh")
    async def user_refresh_action(
        request: Request,
        user_id: str,
        session: AdminSession = Depends(_require_session),
        csrf_token: Annotated[str | None, Form()] = None,
    ) -> RedirectResponse:
        _verify_csrf(request, csrf_token)
        status, body = await post_admin_action(f"/api/admin/users/{user_id}/refresh")
        audit_action(
            actor=session.username,
            action="user_refresh",
            detail=f"user_id={user_id} status={status} body={body[:200]}",
        )
        notice = "refresh_ok" if status < 300 else "refresh_failed"
        return RedirectResponse(
            url=f"/admin/users/{user_id}?notice={notice}", status_code=303
        )

    @app.post("/admin/users/{user_id}/logout")
    async def user_logout_action(
        request: Request,
        user_id: str,
        session: AdminSession = Depends(_require_session),
        csrf_token: Annotated[str | None, Form()] = None,
    ) -> RedirectResponse:
        _verify_csrf(request, csrf_token)
        status, body = await post_admin_action(f"/api/admin/users/{user_id}/logout")
        audit_action(
            actor=session.username,
            action="user_logout",
            detail=f"user_id={user_id} status={status} body={body[:200]}",
        )
        notice = "logout_ok" if status < 300 else "logout_failed"
        return RedirectResponse(
            url=f"/admin/users/{user_id}?notice={notice}", status_code=303
        )

    @app.post("/admin/users/{user_id}/shares/{share_id}/revoke")
    async def user_share_revoke_action(
        request: Request,
        user_id: str,
        share_id: str,
        session: AdminSession = Depends(_require_session),
        csrf_token: Annotated[str | None, Form()] = None,
    ) -> RedirectResponse:
        _verify_csrf(request, csrf_token)
        status, body = await post_admin_action(f"/api/admin/shares/{share_id}/revoke")
        audit_action(
            actor=session.username,
            action="share_revoke",
            detail=f"share_id={share_id} user_id={user_id} status={status} body={body[:200]}",
        )
        notice = "revoke_ok" if status < 300 else "revoke_failed"
        return RedirectResponse(
            url=f"/admin/users/{user_id}?notice={notice}", status_code=303
        )

    @app.post("/admin/users/{user_id}/api-key/revoke")
    async def user_api_key_revoke_action(
        request: Request,
        user_id: str,
        session: AdminSession = Depends(_require_session),
        csrf_token: Annotated[str | None, Form()] = None,
    ) -> RedirectResponse:
        _verify_csrf(request, csrf_token)
        status, body = await post_admin_action(f"/api/admin/users/{user_id}/api-key/revoke")
        audit_action(
            actor=session.username,
            action="api_key_revoke",
            detail=f"user_id={user_id} status={status} body={body[:200]}",
        )
        notice = "api_key_revoke_ok" if status < 300 else "api_key_revoke_failed"
        return RedirectResponse(
            url=f"/admin/users/{user_id}?notice={notice}", status_code=303
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
        notice = request.query_params.get("notice")
        cleared_raw = request.query_params.get("n", "0")
        try:
            cleared_n = max(0, int(cleared_raw))
        except ValueError:
            cleared_n = 0
        rows = await top_queued_price_estimate_jobs(limit=50)
        await enrich_price_queue_rows(rows)
        return TEMPLATES.TemplateResponse(
            request,
            "price_queue.html",
            {
                "session": session,
                "active": "price_queue",
                "rows": rows,
                "notice": notice,
                "cleared_n": cleared_n,
            },
        )

    @app.post("/admin/price-queue/remove")
    async def price_queue_remove(
        request: Request,
        job_id: Annotated[str, Form()],
        session: AdminSession = Depends(_require_session),
        csrf_token: Annotated[str | None, Form()] = None,
    ) -> RedirectResponse:
        _verify_csrf(request, csrf_token)
        ok, outcome = await delete_price_job_key(job_id)
        audit_action(
            actor=session.username,
            action="price_queue_remove",
            detail=f"job_id={job_id} outcome={outcome}",
        )
        if not ok:
            return RedirectResponse(url="/admin/price-queue?notice=invalid_job", status_code=303)
        if outcome == "deleted":
            return RedirectResponse(url="/admin/price-queue?notice=removed", status_code=303)
        return RedirectResponse(url="/admin/price-queue?notice=missing", status_code=303)

    @app.post("/admin/price-queue/clear")
    async def price_queue_clear(
        request: Request,
        session: AdminSession = Depends(_require_session),
        csrf_token: Annotated[str | None, Form()] = None,
    ) -> RedirectResponse:
        _verify_csrf(request, csrf_token)
        n = await clear_inflight_price_estimate_jobs()
        audit_action(
            actor=session.username,
            action="price_queue_clear",
            detail=f"cleared={n}",
        )
        return RedirectResponse(url=f"/admin/price-queue?notice=cleared&n={n}", status_code=303)

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
