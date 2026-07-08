"""Append-only user login / refresh events for admin analytics.

Revision ID: 0009_user_activity_events
Revises: 0008_character_shares
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0009_user_activity_events"
down_revision = "0008_character_shares"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_activity_events",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("event_type", sa.String(length=16), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_user_activity_events_user_id",
        "user_activity_events",
        ["user_id"],
    )
    op.create_index(
        "ix_user_activity_events_created_at",
        "user_activity_events",
        ["created_at"],
    )
    op.create_index(
        "ix_user_activity_events_type_created",
        "user_activity_events",
        ["event_type", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_user_activity_events_type_created", table_name="user_activity_events")
    op.drop_index("ix_user_activity_events_created_at", table_name="user_activity_events")
    op.drop_index("ix_user_activity_events_user_id", table_name="user_activity_events")
    op.drop_table("user_activity_events")
