"""FastAPI application factory and entrypoint."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api import (
    auth_router,
    characters_router,
    health_router,
    leagues_router,
    me_router,
    prefs_router,
    pricing_router,
    refresh_router,
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
    app = FastAPI(
        title="PoE2 Hideout Butler API",
        version=__version__,
        lifespan=lifespan,
    )

    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
        allow_headers=["Content-Type", "X-CSRF-Token"],
        max_age=600,
    )

    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(me_router)
    app.include_router(leagues_router)
    app.include_router(characters_router)
    app.include_router(refresh_router)
    app.include_router(trade_router)
    app.include_router(prefs_router)
    app.include_router(stashes_router)
    app.include_router(pricing_router)

    return app


app = create_app()
