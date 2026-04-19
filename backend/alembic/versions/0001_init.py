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

    # Create the enum type via a PL/pgSQL guard so the migration is idempotent.
    # Using op.create_table with sa.Enum triggers a SQLAlchemy before_create
    # event that ignores create_type=False in SQLAlchemy 2.0.x, so we own the
    # full lifecycle via raw DDL.
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_type WHERE typname = 'snapshot_kind'
            ) THEN
                CREATE TYPE snapshot_kind AS ENUM (
                    'profile', 'leagues', 'characters',
                    'character', 'stash_list', 'stash_tab'
                );
            END IF;
        END
        $$;
        """
    )

    # Build the snapshots table with raw DDL to avoid SQLAlchemy re-emitting
    # CREATE TYPE snapshot_kind via the Enum column before_create event.
    op.execute(
        """
        CREATE TABLE snapshots (
            id          BIGSERIAL PRIMARY KEY,
            user_id     UUID        NOT NULL
                            REFERENCES users(id) ON DELETE CASCADE,
            kind        snapshot_kind NOT NULL,
            key         VARCHAR(200)  NOT NULL DEFAULT '',
            payload     JSONB         NOT NULL DEFAULT '{}',
            fetched_at  TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
            CONSTRAINT  uq_snapshot_user_kind_key
                UNIQUE (user_id, kind, key)
        )
        """
    )
    op.execute("CREATE INDEX ix_snapshots_user_id ON snapshots (user_id)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_snapshots_user_id")
    op.execute("DROP TABLE IF EXISTS snapshots")
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM pg_type WHERE typname = 'snapshot_kind'
            ) THEN
                DROP TYPE snapshot_kind;
            END IF;
        END
        $$;
        """
    )
    op.drop_table("user_tokens")
    op.drop_index("ix_users_ggg_account_name", table_name="users")
    op.drop_table("users")
