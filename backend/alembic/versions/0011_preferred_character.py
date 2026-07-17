"""Add preferred_character_name to users for bot 'set active character' command.

Revision ID: 0011_preferred_character
Revises: 0010_user_api_keys
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0011_preferred_character"
down_revision = "0010_user_api_keys"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("preferred_character_name", sa.String(length=200), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "preferred_character_name")
