"""worker_heartbeats: when each grading worker last polled the queue

Revision ID: e3a1d6b8c20f
Revises: 9c2e4f7a1b35
Create Date: 2026-10-26 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e3a1d6b8c20f"
down_revision: str | Sequence[str] | None = "9c2e4f7a1b35"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "worker_heartbeats",
        sa.Column("worker_id", sa.String(length=64), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("worker_id"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("worker_heartbeats")
