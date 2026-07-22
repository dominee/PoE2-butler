"""FastAPI application factory and entrypoint."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi

from app import __version__
from app.api import (
    activity_router,
    admin_ops_router,
    api_keys_router,
    auth_router,
    cdn_proxy_router,
    character_shares_router,
    characters_router,
    health_router,
    items_router,
    leagues_router,
    me_router,
    prefs_router,
    pricing_router,
    public_character_router,
    public_item_router,
    refresh_router,
    shares_router,
    stashes_router,
    trade_router,
)
from app.config import get_settings
from app.logging import configure_logging, get_logger
from app.middleware import RequestIdMiddleware, SecurityHeadersMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)
    log = get_logger("app.main")
    log.info("application.start", environment=settings.environment, version=__version__)
    yield
    log.info("application.stop")


def create_app() -> FastAPI:
    settings = get_settings()

    docs_url = "/docs" if settings.expose_docs else None
    redoc_url = "/redoc" if settings.expose_docs else None
    openapi_url = "/openapi.json" if settings.expose_docs else None

    app = FastAPI(
        title="PoE2 Hideout Butler API",
        description=(
            "REST API for PoE2 Hideout Butler. "
            "Browser clients authenticate via session cookie + CSRF. "
            "Machine clients (Discord bot, integrations) authenticate via "
            "`Authorization: Bearer hob_…` API key obtained from `/api/me/api-key`."
        ),
        version=__version__,
        lifespan=lifespan,
        docs_url=docs_url,
        redoc_url=redoc_url,
        openapi_url=openapi_url,
        servers=[{"url": settings.api_base_url, "description": settings.environment}],
    )

    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "X-CSRF-Token", "Authorization"],
        max_age=600,
    )

    app.include_router(health_router)
    app.include_router(admin_ops_router)
    app.include_router(cdn_proxy_router)
    app.include_router(public_item_router)
    app.include_router(public_character_router)
    app.include_router(auth_router)
    app.include_router(api_keys_router)
    app.include_router(shares_router)
    app.include_router(character_shares_router)
    app.include_router(activity_router)
    app.include_router(me_router)
    app.include_router(leagues_router)
    app.include_router(characters_router)
    app.include_router(refresh_router)
    app.include_router(trade_router)
    app.include_router(items_router)
    app.include_router(prefs_router)
    app.include_router(stashes_router)
    app.include_router(pricing_router)

    if settings.expose_docs:
        _patch_openapi(app)

    return app


def _patch_openapi(app: FastAPI) -> None:
    """Add Bearer security scheme to the OpenAPI spec so Swagger UI shows the Authorize button."""

    def custom_openapi():
        if app.openapi_schema:
            return app.openapi_schema
        schema = get_openapi(
            title=app.title,
            version=app.version,
            description=app.description,
            routes=app.routes,
            servers=app.servers,
        )
        schema.setdefault("components", {}).setdefault("securitySchemes", {})["BearerApiKey"] = {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "hob_<prefix>_<secret>",
            "description": (
                "API key for machine clients (Discord bot, etc.). "
                "Obtain via POST /api/me/api-key (requires browser session). "
                "Pass as: Authorization: Bearer hob_…"
            ),
        }
        app.openapi_schema = schema
        return schema

    app.openapi = custom_openapi  # type: ignore[method-assign]


app = create_app()
