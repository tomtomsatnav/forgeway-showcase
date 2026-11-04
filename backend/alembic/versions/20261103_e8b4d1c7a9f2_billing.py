"""billing: the Stripe subscription mirror, processed webhook events and regulation-37 consents

Additive only: three new tables, nothing existing changes, so the previous release keeps working
against the upgraded schema. `users.plan` stays the column entitlements read; billing writes it.

Revision ID: e8b4d1c7a9f2
Revises: c5f1a8e2d7b4
Create Date: 2026-11-03 15:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e8b4d1c7a9f2"
down_revision: str | Sequence[str] | None = "c5f1a8e2d7b4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "subscriptions",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("stripe_customer_id", sa.String(length=255), nullable=False),
        sa.Column("stripe_subscription_id", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=True),
        sa.Column("interval", sa.String(length=8), nullable=True),
        sa.Column("price_id", sa.String(length=255), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("trial_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancel_at_period_end", sa.Boolean(), nullable=False),
        sa.Column("cancel_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paused", sa.Boolean(), nullable=False),
        sa.Column("resumes_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("latest_invoice_id", sa.String(length=255), nullable=True),
        sa.Column("country", sa.String(length=2), nullable=True),
        sa.Column("trial_used", sa.Boolean(), nullable=False),
        sa.Column("onboarding_nudged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
        sa.UniqueConstraint("stripe_customer_id"),
        sa.UniqueConstraint("stripe_subscription_id"),
    )
    op.create_table(
        "billing_events",
        sa.Column("id", sa.String(length=255), nullable=False),
        sa.Column("type", sa.String(length=64), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "billing_consents",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("wording_version", sa.String(length=32), nullable=False),
        sa.Column("wording", sa.Text(), nullable=False),
        sa.Column("plan", sa.String(length=8), nullable=False),
        sa.Column("checkout_session_id", sa.String(length=255), nullable=True),
        sa.CheckConstraint("plan IN ('monthly', 'annual')", name="consent_plan_valid"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_billing_consents_user", "billing_consents", ["user_id", "created_at"])
    op.create_index("ix_billing_consents_session", "billing_consents", ["checkout_session_id"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_billing_consents_session", table_name="billing_consents")
    op.drop_index("ix_billing_consents_user", table_name="billing_consents")
    op.drop_table("billing_consents")
    op.drop_table("billing_events")
    op.drop_table("subscriptions")
