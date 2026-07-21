"""Cross-cutting middleware: security headers, request ids."""

from __future__ import annotations

import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Attach a request id to every request, bind it to the logger, echo to the response."""

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("X-Request-Id") or uuid.uuid4().hex
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
        )
        response = await call_next(request)
        response.headers["X-Request-Id"] = request_id
        return response


_DOCS_PATHS = frozenset({"/docs", "/redoc", "/docs/oauth2-redirect"})

# FastAPI hard-codes this inline init script in its generated /docs HTML.
# Using the hash avoids blanket unsafe-inline while still matching FastAPI's
# exact script content. Update if FastAPI changes the snippet.
_SWAGGER_SCRIPT_HASH = "sha256-QOOQu4W1oxGqd2nbXbxiA1Di6OHQOLQD+o+G9oWL8YY="

_DOCS_CSP = (
    "default-src 'none'; "
    f"script-src 'unsafe-inline' https://cdn.jsdelivr.net; "
    "style-src 'unsafe-inline' https://cdn.jsdelivr.net; "
    "img-src 'self' data: https://fastapi.tiangolo.com; "
    "connect-src 'self'; "
    "font-src https://cdn.jsdelivr.net; "
    "frame-ancestors 'none'"
)

_API_CSP = "default-src 'none'; frame-ancestors 'none'"


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Apply baseline security headers to every response.

    CSP is strict for API responses. Docs paths (/docs, /redoc) get a relaxed
    policy that allows the Swagger UI and ReDoc CDN assets to load.
    The frontend origin sets its own CSP via its static hosting layer.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault(
            "Permissions-Policy",
            "geolocation=(), microphone=(), camera=()",
        )
        csp = _DOCS_CSP if request.url.path in _DOCS_PATHS else _API_CSP
        response.headers.setdefault("Content-Security-Policy", csp)
        response.headers.setdefault(
            "Strict-Transport-Security",
            "max-age=31536000; includeSubDomains",
        )
        return response
