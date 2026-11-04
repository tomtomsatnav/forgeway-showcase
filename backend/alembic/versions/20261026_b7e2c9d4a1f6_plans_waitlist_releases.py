"""plans, the Pro waitlist and the last-seen release

Every existing account becomes `free` (the column's server default), which keeps everyone's
progress: entitlements gate new attempts only, never what was already passed.

Revision ID: b7e2c9d4a1f6
Revises: d4049b750eea
Create Date: 2026-10-26 18:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b7e2c9d4a1f6"
down_revision: str | Sequence[str] | None = "d4049b750eea"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "users", sa.Column("plan", sa.String(length=8), server_default="free", nullable=False)
    )
    op.create_check_constraint("plan_valid", "users", "plan IN ('free', 'pro', 'team')")
    op.add_column(
        "learner_profiles", sa.Column("last_seen_release", sa.String(length=32), nullable=True)
    )
    op.create_table(
        "pro_waitlist",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("plan_interest", sa.String(length=8), nullable=False),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("plan_interest IN ('pro', 'team')", name="plan_interest_valid"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("pro_waitlist")
    op.drop_column("learner_profiles", "last_seen_release")
    op.drop_constraint("plan_valid", "users", type_="check")
    op.drop_column("users", "plan")
