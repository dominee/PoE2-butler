"""Proxy official PoE CDN item icons (same-origin for canvas) — allowlist only."""

from __future__ import annotations

from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Response

from app.db.models import User
from app.deps import get_current_user

POECDN = "web.poecdn.com"

router = APIRouter(prefix="/api/cdn", tags=["cdn"])


@router.get(
    "/poecdn",
    response_class=Response,
    summary="Proxy a web.poecdn.com image (canvas-safe; allowlisted host only)",
)
async def proxy_poecdn(
    u: str = Query(
        ..., min_length=8, max_length=6000, description="Full https://web.poecdn.com/… URL"
    ),
    _user: User = Depends(get_current_user),
) -> Response:
    parsed = urlparse(u)
    if parsed.scheme != "https" or (parsed.netloc or "").lower() != POECDN:
        raise HTTPException(status_code=400, detail="invalid_cdn_url")
    if not (parsed.path or "/").strip("/"):
        raise HTTPException(status_code=400, detail="invalid_cdn_url")
    try:
        async with httpx.AsyncClient(timeout=25.0, follow_redirects=True) as client:
            r = await client.get(
                u,
                headers={"User-Agent": "PoE2HideoutButler/1 (item icon; contact: dev@hell.sk)"},
            )
    except httpx.RequestError as exc:  # pragma: no cover - network in prod
        raise HTTPException(status_code=502, detail="upstream_unavailable") from exc
    if r.status_code != 200:
        raise HTTPException(status_code=502, detail="upstream_error")
    content_type = (r.headers.get("content-type") or "image/png").split(";")[0].strip()
    if not content_type.startswith("image/"):
        raise HTTPException(status_code=502, detail="not_image")
    return Response(
        content=r.content,
        media_type=content_type,
        headers={"Cache-Control": "public, max-age=86400"},
    )
