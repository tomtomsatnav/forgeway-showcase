"""withdrawal cancel failed: when a withdrawal was refunded but Stripe would not cancel

Additive: one nullable column. The previous release keeps working against it.

Revision ID: a3d9e5f1c2b8
Revises: f2a7c3e9b1d6
Create Date: 2026-11-03 21:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a3d9e5f1c2b8"
down_revision: str | Sequence[str] | None = "f2a7c3e9b1d6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "subscriptions",
        sa.Column("withdrawal_cancel_failed_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("subscriptions", "withdrawal_cancel_failed_at")
