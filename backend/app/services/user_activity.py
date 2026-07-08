"""Record user login and refresh events for admin analytics."""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import UserActivityEvent, UserActivityEventType


async def record_user_activity(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    event_type: UserActivityEventType,
) -> None:
    session.add(UserActivityEvent(user_id=user_id, event_type=event_type))
