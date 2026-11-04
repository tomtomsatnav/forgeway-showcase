"""new to python: the learner's preference for the "Python you'll need" notes

Additive: one defaulted column. The previous release keeps working against it.

Revision ID: b7e2c4d9a1f3
Revises: a3d9e5f1c2b8
Create Date: 2026-11-04 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b7e2c4d9a1f3"
down_revision: str | Sequence[str] | None = "a3d9e5f1c2b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "learner_profiles",
        sa.Column("new_to_python", sa.Boolean(), server_default="false", nullable=False),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("learner_profiles", "new_to_python")
