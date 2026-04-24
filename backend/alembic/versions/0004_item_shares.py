"""Public item share links (UUID → frozen item JSON).

Revision ID: 0004_item_shares
Revises: 0003_prev_payload
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0004_item_shares"
down_revision = "0003_prev_payload"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "item_shares",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("league", sa.String(length=200), nullable=False),
        sa.Column("item_raw", postgresql.JSONB, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_item_shares_user_id", "item_shares", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_item_shares_user_id", table_name="item_shares")
    op.drop_table("item_shares")
