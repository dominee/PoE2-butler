"""HTTP calls from admin to backend operator routes."""

from __future__ import annotations

import httpx

from admin.app.config import get_admin_settings


async def post_admin_action(path: str) -> tuple[int, str]:
    settings = get_admin_settings()
    secret = settings.internal_secret.get_secret_value().strip()
    if not secret:
        return 503, "ADMIN_INTERNAL_SECRET not configured"
    url = f"{settings.backend_base_url.rstrip('/')}{path}"
    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(url, headers={"X-Admin-Internal-Secret": secret})
    body = resp.text.strip()[:500]
    return resp.status_code, body
