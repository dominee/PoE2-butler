"""Add prev_payload to snapshots for activity-log diffing.

Revision ID: 0003_prev_payload
Revises: 0002_valuable_threshold
Create Date: 2026-04-20
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "0003_prev_payload"
down_revision = "0002_valuable_threshold"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "snapshots",
        sa.Column(
            "prev_payload",
            # Use JSONB on Postgres, plain JSON on SQLite (tests).
            JSONB().with_variant(sa.JSON(), "sqlite"),
            nullable=True,
            server_default=None,
        ),
    )


def downgrade() -> None:
    op.drop_column("snapshots", "prev_payload")
