"""live runs: runs, the cost of each proxied model call and data-notice acknowledgements

In-app live runs (ADR 0012). Additive only: three new tables, nothing existing changes, so the
previous release keeps working against the upgraded schema.

Revision ID: c5f1a8e2d7b4
Revises: b7e2c9d4a1f6
Create Date: 2026-11-03 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "c5f1a8e2d7b4"
down_revision: str | Sequence[str] | None = "b7e2c9d4a1f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "live_runs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("exercise_id", sa.String(length=130), nullable=False),
        sa.Column("files", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("worker_id", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'finished', 'errored')", name="live_run_status_valid"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_live_runs_user_created", "live_runs", ["user_id", "created_at"])
    op.create_index(
        "ix_live_runs_queue",
        "live_runs",
        ["created_at"],
        postgresql_where=sa.text("status = 'queued'"),
    )
    op.create_index(
        "uq_live_runs_in_flight",
        "live_runs",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('queued', 'running')"),
    )
    op.create_table(
        "live_calls",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("run_id", sa.UUID(), nullable=True),
        sa.Column("exercise_id", sa.String(length=130), nullable=False),
        sa.Column("model", sa.String(length=64), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("cache_read_tokens", sa.Integer(), nullable=False),
        sa.Column("cache_write_tokens", sa.Integer(), nullable=False),
        sa.Column("cost_usd", sa.Numeric(precision=14, scale=8), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("outcome", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id"], ["live_runs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_live_calls_user_created", "live_calls", ["user_id", "created_at"])
    op.create_index("ix_live_calls_created", "live_calls", ["created_at"])
    op.create_table(
        "live_notice_acknowledgements",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("version", sa.String(length=32), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "version", name="uq_live_notice_once_per_version"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("live_notice_acknowledgements")
    op.drop_index("ix_live_calls_created", table_name="live_calls")
    op.drop_index("ix_live_calls_user_created", table_name="live_calls")
    op.drop_table("live_calls")
    op.drop_index("uq_live_runs_in_flight", table_name="live_runs")
    op.drop_index("ix_live_runs_queue", table_name="live_runs")
    op.drop_index("ix_live_runs_user_created", table_name="live_runs")
    op.drop_table("live_runs")
