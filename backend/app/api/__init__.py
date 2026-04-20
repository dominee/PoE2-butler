"""API routers."""

from app.api.activity import router as activity_router
from app.api.auth import router as auth_router
from app.api.characters import router as characters_router
from app.api.health import router as health_router
from app.api.leagues import router as leagues_router
from app.api.me import router as me_router
from app.api.prefs import router as prefs_router
from app.api.pricing import router as pricing_router
from app.api.refresh import router as refresh_router
from app.api.stashes import router as stashes_router
from app.api.trade import router as trade_router

__all__ = [
    "activity_router",
    "auth_router",
    "characters_router",
    "health_router",
    "leagues_router",
    "me_router",
    "prefs_router",
    "pricing_router",
    "refresh_router",
    "stashes_router",
    "trade_router",
]
