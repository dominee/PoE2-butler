"""Public character share links (UUID → frozen CharacterDetail JSON).

Revision ID: 0008_character_shares
Revises: 0007_character_snapshot_changes
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0008_character_shares"
down_revision = "0007_character_snapshot_changes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "character_shares",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("league", sa.String(length=200), nullable=False),
        sa.Column("character_name", sa.String(length=200), nullable=False),
        sa.Column("character_raw", postgresql.JSONB, nullable=False),
        sa.Column("view_mode", sa.String(length=16), nullable=False, server_default="simple"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_index("ix_character_shares_user_id", table_name="character_shares")
    op.drop_table("character_shares")
