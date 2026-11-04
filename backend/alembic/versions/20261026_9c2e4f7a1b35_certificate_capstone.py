"""certificates: record whether the branch had a capstone when issued

Revision ID: 9c2e4f7a1b35
Revises: 7d3f9a1c4e62
Create Date: 2026-10-26 09:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9c2e4f7a1b35"
down_revision: str | Sequence[str] | None = "7d3f9a1c4e62"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema. Existing certificates predate capstones, so they do not claim one."""
    op.add_column(
        "certificates",
        sa.Column("includes_capstone", sa.Boolean(), server_default="false", nullable=False),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("certificates", "includes_capstone")
