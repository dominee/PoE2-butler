"""Archive table for historic character gear snapshots (timeline UI).

Revision ID: 0006_character_snapshot_history
Revises: 0005_item_price_estimates
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0006_character_snapshot_history"
down_revision = "0005_item_price_estimates"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "character_snapshot_history",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("character_name", sa.String(length=200), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_char_snap_hist_user_name_fetched",
        "character_snapshot_history",
        ["user_id", "character_name", "fetched_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_char_snap_hist_user_name_fetched", table_name="character_snapshot_history")
    op.drop_table("character_snapshot_history")
