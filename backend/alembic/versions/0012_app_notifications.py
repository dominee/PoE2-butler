"""Add app_notifications table for admin-managed SPA notifications.

Revision ID: 0012_app_notifications
Revises: 0011_preferred_character
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0012_app_notifications"
down_revision = "0011_preferred_character"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "app_notifications",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("message", sa.String(length=2000), nullable=False),
        sa.Column("notification_type", sa.String(length=20), nullable=False, server_default="info"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_app_notifications_active", "app_notifications", ["active"])


def downgrade() -> None:
    op.drop_index("ix_app_notifications_active", table_name="app_notifications")
    op.drop_table("app_notifications")
