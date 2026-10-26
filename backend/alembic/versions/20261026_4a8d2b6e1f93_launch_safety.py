"""launch safety: email verification, account tokens, rate-limit hits, one attempt in flight

Revision ID: 4a8d2b6e1f93
Revises: 9c2e4f7a1b35
Create Date: 2026-10-26 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "4a8d2b6e1f93"
down_revision: str | Sequence[str] | None = "9c2e4f7a1b35"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SUPERSEDED = (
    '{"status": "errored", "checks": [], "error": "Superseded: only one attempt is graded at a '
    'time now. This attempt does not count against you."}'
)


def upgrade() -> None:
    """Upgrade schema.

    Accounts that already exist were made before verification and count as verified. A learner
    with several attempts in flight keeps the oldest; the rest are errored, which never counts
    against them.
    """
    op.add_column("users", sa.Column("email_verified_at", sa.DateTime(timezone=True)))
    op.add_column("users", sa.Column("pending_email", sa.String(length=254)))
    op.execute("UPDATE users SET email_verified_at = created_at")

    op.create_table(
        "account_tokens",
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("purpose", sa.String(length=16), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("purpose IN ('verify-email', 'reset-password')", name="purpose_valid"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("token_hash"),
    )
    op.create_index(
        "ix_account_tokens_user_purpose", "account_tokens", ["user_id", "purpose"], unique=False
    )

    op.create_table(
        "rate_limit_hits",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("key", sa.String(length=320), nullable=False),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_rate_limit_hits_key_at", "rate_limit_hits", ["key", "at"], unique=False)
    op.create_index("ix_rate_limit_hits_at", "rate_limit_hits", ["at"], unique=False)

    op.execute(
        f"""
        UPDATE attempts SET status = 'errored', finished_at = now(), report = '{_SUPERSEDED}'
        WHERE status IN ('queued', 'running') AND id NOT IN (
            SELECT DISTINCT ON (user_id) id FROM attempts
            WHERE status IN ('queued', 'running')
            ORDER BY user_id, created_at
        )
        """  # noqa: S608 - a constant
    )
    op.drop_index("uq_attempts_in_flight", table_name="attempts")
    op.create_index(
        "uq_attempts_in_flight",
        "attempts",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('queued', 'running')"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("uq_attempts_in_flight", table_name="attempts")
    op.create_index(
        "uq_attempts_in_flight",
        "attempts",
        ["user_id", "exercise_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('queued', 'running')"),
    )
    op.drop_index("ix_rate_limit_hits_at", table_name="rate_limit_hits")
    op.drop_index("ix_rate_limit_hits_key_at", table_name="rate_limit_hits")
    op.drop_table("rate_limit_hits")
    op.drop_index("ix_account_tokens_user_purpose", table_name="account_tokens")
    op.drop_table("account_tokens")
    op.drop_column("users", "pending_email")
    op.drop_column("users", "email_verified_at")
