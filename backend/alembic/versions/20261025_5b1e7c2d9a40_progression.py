"""progression: talents, badges, time zones and stamped local days

Revision ID: 5b1e7c2d9a40
Revises: ca84b47f949a
Create Date: 2026-10-25 18:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "5b1e7c2d9a40"
down_revision: str | Sequence[str] | None = "ca84b47f949a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "talent_allocations",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("node_id", sa.String(length=64), nullable=False),
        sa.Column("allocated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "node_id", name="uq_talent_once"),
    )
    op.create_table(
        "badge_awards",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("badge_id", sa.String(length=64), nullable=False),
        sa.Column("attempt_id", sa.UUID(), nullable=False),
        sa.Column("awarded_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["attempt_id"], ["attempts.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "badge_id", name="uq_badge_once"),
    )
    op.add_column(
        "learner_profiles",
        sa.Column("time_zone", sa.String(length=64), nullable=False, server_default="UTC"),
    )
    op.alter_column("learner_profiles", "time_zone", server_default=None)
    op.add_column("attempts", sa.Column("files_hash", sa.String(length=64), nullable=True))
    # Existing attempts are stamped with their UTC date, the zone every profile starts in.
    op.add_column("attempts", sa.Column("local_day", sa.Date(), nullable=True))
    op.execute("UPDATE attempts SET local_day = (created_at AT TIME ZONE 'UTC')::date")
    op.alter_column("attempts", "local_day", nullable=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("attempts", "local_day")
    op.drop_column("attempts", "files_hash")
    op.drop_column("learner_profiles", "time_zone")
    op.drop_table("badge_awards")
    op.drop_table("talent_allocations")
