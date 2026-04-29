"""Persisted hybrid price estimates per user / league / stash item id.

Revision ID: 0005_item_price_estimates
Revises: 0004_item_shares
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0005_item_price_estimates"
down_revision = "0004_item_shares"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "item_price_estimates",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("league", sa.String(length=200), nullable=False),
        sa.Column("item_id", sa.String(length=128), nullable=False),
        sa.Column("tolerance_pct", sa.Float(), nullable=False),
        sa.Column("item_name", sa.String(length=200), nullable=False, server_default=""),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("message", sa.String(length=500), nullable=True),
        sa.Column("error", sa.String(length=500), nullable=True),
        sa.Column("result_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "computed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "league", "item_id", name="uq_item_price_user_league_item"),
    )
    op.create_index(
        "ix_item_price_estimates_user_league",
        "item_price_estimates",
        ["user_id", "league"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_item_price_estimates_user_league", table_name="item_price_estimates")
    op.drop_table("item_price_estimates")
