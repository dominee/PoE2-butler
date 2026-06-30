"""Add changes JSON to character snapshot history for timeline diffs.

Revision ID: 0007_character_snapshot_changes
Revises: 0006_character_snapshot_history
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0007_character_snapshot_changes"
down_revision = "0006_character_snapshot_history"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "character_snapshot_history",
        sa.Column(
            "changes",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
    )


def downgrade() -> None:
    op.drop_column("character_snapshot_history", "changes")
