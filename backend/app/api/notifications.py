"""Public notifications endpoint — no auth required.

Returns active, non-expired notifications for display in the SPA.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_session
from app.db.models import AppNotification

router = APIRouter(tags=["notifications"])


class NotificationOut(BaseModel):
    id: UUID
    title: str
    message: str
    notification_type: str
    created_at: datetime

    model_config = {"from_attributes": True}


@router.get(
    "/api/notifications",
    response_model=list[NotificationOut],
    summary="Active notifications",
)
async def get_notifications(
    db: AsyncSession = Depends(get_session),
) -> list[AppNotification]:
    """Return active notifications that have not yet expired.

    No authentication required — intended for display to all SPA users.
    """
    now = datetime.now(UTC)
    result = await db.execute(
        select(AppNotification)
        .where(AppNotification.active.is_(True))
        .where(
            (AppNotification.expires_at.is_(None)) | (AppNotification.expires_at > now)
        )
        .order_by(AppNotification.created_at.desc())
    )
    return list(result.scalars().all())
