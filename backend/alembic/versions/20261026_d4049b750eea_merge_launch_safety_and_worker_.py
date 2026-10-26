"""Merge the launch-safety and worker-heartbeat branches of the schema.

Revision ID: d4049b750eea
Revises: 4a8d2b6e1f93, e3a1d6b8c20f
Create Date: 2026-10-26
"""

from collections.abc import Sequence

revision: str = "d4049b750eea"
down_revision: str | Sequence[str] | None = ("4a8d2b6e1f93", "e3a1d6b8c20f")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Nothing to do: both branches' changes are independent."""


def downgrade() -> None:
    """Nothing to do: both branches' changes are independent."""
