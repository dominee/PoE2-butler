"""Initial schema: users, user_tokens, snapshots.

Revision ID: 0001_init
Revises:
Create Date: 2026-04-19
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0001_init"
down_revision = None
branch_labels = None
depends_on = None


SNAPSHOT_KIND = sa.Enum(
    "profile",
    "leagues",
    "characters",
    "character",
    "stash_list",
    "stash_tab",
    name="snapshot_kind",
)


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("ggg_account_name", sa.String(length=200), nullable=False, unique=True),
        sa.Column("ggg_uuid", sa.String(length=64), nullable=True),
        sa.Column("realm", sa.String(length=16), nullable=False, server_default="pc"),
        sa.Column("preferred_league", sa.String(length=200), nullable=True),
        sa.Column("trade_tolerance_pct", sa.Integer(), nullable=False, server_default="10"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_refreshed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_users_ggg_account_name", "users", ["ggg_account_name"], unique=True
    )

    op.create_table(
        "user_tokens",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("access_token_enc", sa.LargeBinary(), nullable=False),
        sa.Column("refresh_token_enc", sa.LargeBinary(), nullable=True),
        sa.Column("scope", sa.String(length=500), nullable=False, server_default=""),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    SNAPSHOT_KIND.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "snapshots",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kind", SNAPSHOT_KIND, nullable=False),
        sa.Column("key", sa.String(length=200), nullable=False, server_default=""),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("user_id", "kind", "key", name="uq_snapshot_user_kind_key"),
    )
    op.create_index("ix_snapshots_user_id", "snapshots", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_snapshots_user_id", table_name="snapshots")
    op.drop_table("snapshots")
    SNAPSHOT_KIND.drop(op.get_bind(), checkfirst=True)
    op.drop_table("user_tokens")
    op.drop_index("ix_users_ggg_account_name", table_name="users")
    op.drop_table("users")
