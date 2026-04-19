"""Add valuable_threshold_chaos to users.

Revision ID: 0002_valuable_threshold
Revises: 0001_init
Create Date: 2026-04-19
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0002_valuable_threshold"
down_revision = "0001_init"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "valuable_threshold_chaos",
            sa.Integer(),
            nullable=False,
            server_default="100",
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "valuable_threshold_chaos")
