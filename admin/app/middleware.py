"""IP allowlist + security headers for the admin console."""

from __future__ import annotations

from ipaddress import ip_address, ip_network

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response


class IPAllowlistMiddleware(BaseHTTPMiddleware):
    """Reject clients whose remote address is not in the configured CIDR list.

    An empty allowlist disables the check so dev stacks stay frictionless.
    """

    def __init__(self, app, allowlist: list[str]) -> None:
        super().__init__(app)
        self._networks = [ip_network(entry, strict=False) for entry in allowlist if entry]

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        if not self._networks:
            return await call_next(request)
        client = request.client.host if request.client else ""
        try:
            addr = ip_address(client)
        except ValueError:
            return PlainTextResponse("forbidden", status_code=403)
        if not any(addr in net for net in self._networks):
            return PlainTextResponse("forbidden", status_code=403)
        return await call_next(request)


class AdminSecurityHeaders(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[override]
        response = await call_next(request)
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'",
        )
        return response
