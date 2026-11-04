"""legal compliance: terms acceptance, the marketing opt-out, unsubscribe tokens, and billing
consents that outlive the account

Additive: new nullable or defaulted columns, a wider check constraint, and `billing_consents`'
foreign key changes from CASCADE to SET NULL (so deleting an account keeps its pseudonymised
consent as evidence of the regulation-37 waiver). The previous release keeps working against it.

Revision ID: f2a7c3e9b1d6
Revises: e8b4d1c7a9f2
Create Date: 2026-11-03 18:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f2a7c3e9b1d6"
down_revision: str | Sequence[str] | None = "e8b4d1c7a9f2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CONSENT_FK = "billing_consents_user_id_fkey"  # Postgres' default name for the original key


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("users", sa.Column("terms_version", sa.String(length=32), nullable=True))
    op.add_column(
        "users", sa.Column("terms_accepted_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "learner_profiles",
        sa.Column("marketing_opt_out", sa.Boolean(), server_default="false", nullable=False),
    )
    op.drop_constraint("purpose_valid", "account_tokens", type_="check")
    op.create_check_constraint(
        "purpose_valid",
        "account_tokens",
        "purpose IN ('verify-email', 'reset-password', 'unsubscribe')",
    )
    op.alter_column("billing_consents", "user_id", existing_type=sa.UUID(), nullable=True)
    op.drop_constraint(_CONSENT_FK, "billing_consents", type_="foreignkey")
    op.create_foreign_key(
        _CONSENT_FK, "billing_consents", "users", ["user_id"], ["id"], ondelete="SET NULL"
    )
    op.add_column(
        "billing_consents", sa.Column("stripe_customer_id", sa.String(length=255), nullable=True)
    )
    op.add_column(
        "billing_consents",
        sa.Column("stripe_subscription_id", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema. Pseudonymised consents (no account) cannot go back under a NOT NULL
    cascade, so they are removed first."""
    op.drop_column("billing_consents", "stripe_subscription_id")
    op.drop_column("billing_consents", "stripe_customer_id")
    op.execute("DELETE FROM billing_consents WHERE user_id IS NULL")
    op.drop_constraint(_CONSENT_FK, "billing_consents", type_="foreignkey")
    op.create_foreign_key(
        _CONSENT_FK, "billing_consents", "users", ["user_id"], ["id"], ondelete="CASCADE"
    )
    op.alter_column("billing_consents", "user_id", existing_type=sa.UUID(), nullable=False)
    op.execute("DELETE FROM account_tokens WHERE purpose = 'unsubscribe'")
    op.drop_constraint("purpose_valid", "account_tokens", type_="check")
    op.create_check_constraint(
        "purpose_valid", "account_tokens", "purpose IN ('verify-email', 'reset-password')"
    )
    op.drop_column("learner_profiles", "marketing_opt_out")
    op.drop_column("users", "terms_accepted_at")
    op.drop_column("users", "terms_version")
