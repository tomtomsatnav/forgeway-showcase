"""certificates: branch-completion credentials with a random public id

Revision ID: 7d3f9a1c4e62
Revises: 5b1e7c2d9a40
Create Date: 2026-10-25 21:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7d3f9a1c4e62"
down_revision: str | Sequence[str] | None = "5b1e7c2d9a40"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "certificates",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("branch_id", sa.String(length=64), nullable=False),
        sa.Column("recipient_name", sa.String(length=60), nullable=False),
        sa.Column("branch_title", sa.String(length=80), nullable=False),
        sa.Column("exercise_count", sa.Integer(), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempt_id", sa.UUID(), nullable=True),
        sa.Column("is_public", sa.Boolean(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("exercise_count > 0", name="exercise_count_positive"),
        sa.ForeignKeyConstraint(["attempt_id"], ["attempts.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "branch_id", name="uq_certificate_once"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("certificates")
