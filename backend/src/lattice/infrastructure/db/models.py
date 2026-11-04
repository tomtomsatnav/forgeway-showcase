"""SQLAlchemy table mappings.

Content is the source of truth on disk; `branches` and `exercise_revisions` hold the public
part of it so progress and attempts can reference stable rows. Private grading assets (tests,
solutions, wrong cases) are never stored here.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any, ClassVar

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from lattice.domain.certificates import new_public_id


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    type_annotation_map: ClassVar[dict[Any, Any]] = {
        dict[str, Any]: JSONB,
        datetime: DateTime(timezone=True),
    }


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(254), unique=True)  # stored lower-cased
    display_name: Mapped[str] = mapped_column(String(60))
    password_hash: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    # Null until the learner follows a verification link; unverified accounts are purged.
    email_verified_at: Mapped[datetime | None] = mapped_column()
    # A requested new address. It replaces `email` only once a link sent to it is followed.
    pending_email: Mapped[str | None] = mapped_column(String(254))
    # `lattice.domain.entitlements.Plan`. Every account starts free; the owner sets Pro by hand
    # (`forgeway accounts set-plan`) until there is billing.
    plan: Mapped[str] = mapped_column(String(8), default="free", server_default="free")
    # The terms the learner last accepted (`accounts.TERMS_VERSION`) and when. Null for accounts
    # made before acceptance was recorded.
    terms_version: Mapped[str | None] = mapped_column(String(32))
    terms_accepted_at: Mapped[datetime | None] = mapped_column()

    __table_args__ = (CheckConstraint("plan IN ('free', 'pro', 'team')", name="plan_valid"),)


class LearnerProfile(Base):
    """Presentation preferences and path choice. Nothing here affects grading."""

    __tablename__ = "learner_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    mode: Mapped[str] = mapped_column(String(16), default="professional")
    colour_scheme: Mapped[str] = mapped_column(String(8), default="system")
    path_choice: Mapped[str | None] = mapped_column(String(64))  # None means the generalist path
    time_zone: Mapped[str] = mapped_column(String(64), default="UTC")  # IANA name
    leaderboard_opt_in: Mapped[bool] = mapped_column(Boolean, default=False)
    # The newest content release the learner has opened "What's new" on; None means never.
    last_seen_release: Mapped[str | None] = mapped_column(String(32))
    # Refused marketing email (PECR reg 22 soft opt-in: customers get offers unless they refuse).
    marketing_opt_out: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    # Show the "Python you'll need" notes on exercises. Presentation only: grading never reads it.
    new_to_python: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    __table_args__ = (
        CheckConstraint("mode IN ('rpg', 'professional')", name="mode_valid"),
        CheckConstraint("colour_scheme IN ('system', 'light', 'dark')", name="scheme_valid"),
    )


class ProWaitlistEntry(Base):
    """A learner who asked to hear when Pro (or Team) opens. One row per learner; no email is
    sent from it. The address is the one the learner had when they last joined."""

    __tablename__ = "pro_waitlist"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    email: Mapped[str] = mapped_column(String(254))
    plan_interest: Mapped[str] = mapped_column(String(8), default="pro")
    joined_at: Mapped[datetime] = mapped_column(default=utcnow)

    __table_args__ = (
        CheckConstraint("plan_interest IN ('pro', 'team')", name="plan_interest_valid"),
    )


class Session(Base):
    """Server-side session. Only a SHA-256 of the cookie token is stored."""

    __tablename__ = "sessions"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    csrf_token: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    expires_at: Mapped[datetime] = mapped_column()

    __table_args__ = (Index("ix_sessions_user_id", "user_id"),)


class AccountToken(Base):
    """An emailed token: email verification, password reset or a marketing unsubscribe link.

    Only a SHA-256 of the token is stored. Verification and reset tokens are deleted when used;
    unsubscribe tokens work until they expire, so a second click still works.
    """

    __tablename__ = "account_tokens"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    purpose: Mapped[str] = mapped_column(String(16))
    email: Mapped[str] = mapped_column(String(254))  # the address the token was sent to
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    expires_at: Mapped[datetime] = mapped_column()

    __table_args__ = (
        CheckConstraint(
            "purpose IN ('verify-email', 'reset-password', 'unsubscribe')", name="purpose_valid"
        ),
        Index("ix_account_tokens_user_purpose", "user_id", "purpose"),
    )


class RateLimitHit(Base):
    """One counted request for a rate-limit key, such as `register:ip:203.0.113.7`.

    Kept in Postgres so limits survive restarts and hold across API processes.
    """

    __tablename__ = "rate_limit_hits"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(320))
    at: Mapped[datetime] = mapped_column(default=utcnow)

    __table_args__ = (
        Index("ix_rate_limit_hits_key_at", "key", "at"),
        Index("ix_rate_limit_hits_at", "at"),
    )


class BranchRow(Base):
    __tablename__ = "branches"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[str] = mapped_column(String(80))
    summary: Mapped[str] = mapped_column(Text)
    position: Mapped[int] = mapped_column(Integer)
    requires: Mapped[list[str]] = mapped_column(ARRAY(String(64)), default=list)


class ExerciseRevision(Base):
    """One immutable snapshot of an exercise's public definition, keyed by content hash."""

    __tablename__ = "exercise_revisions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    exercise_id: Mapped[str] = mapped_column(String(130))
    version: Mapped[int] = mapped_column(Integer)
    content_hash: Mapped[str] = mapped_column(String(64), unique=True)
    definition: Mapped[dict[str, Any]] = mapped_column()
    is_current: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    __table_args__ = (
        Index(
            "uq_exercise_revisions_current",
            "exercise_id",
            unique=True,
            postgresql_where=text("is_current"),
        ),
    )


class Attempt(Base):
    """A submission and, once graded, its report. The row doubles as the grading job."""

    __tablename__ = "attempts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    exercise_id: Mapped[str] = mapped_column(String(130))
    revision_id: Mapped[int] = mapped_column(ForeignKey("exercise_revisions.id"))
    files: Mapped[dict[str, Any]] = mapped_column()
    status: Mapped[str] = mapped_column(String(16), default="queued")
    report: Mapped[dict[str, Any] | None] = mapped_column()
    tries: Mapped[int] = mapped_column(Integer, default=0)
    worker_id: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    # The date at submission in the learner's zone at that moment, never rewritten.
    local_day: Mapped[date] = mapped_column(Date)
    # SHA-256 of the canonical submission; null on attempts that predate duplicate detection.
    files_hash: Mapped[str | None] = mapped_column(String(64))
    claimed_at: Mapped[datetime | None] = mapped_column()
    finished_at: Mapped[datetime | None] = mapped_column()

    __table_args__ = (
        CheckConstraint(
            "status IN ('queued', 'running', 'passed', 'failed', 'errored')", name="status_valid"
        ),
        Index("ix_attempts_user_exercise", "user_id", "exercise_id", "created_at"),
        Index("ix_attempts_queue", "created_at", postgresql_where=text("status = 'queued'")),
        # At most one attempt in flight per learner, across every exercise.
        Index(
            "uq_attempts_in_flight",
            "user_id",
            unique=True,
            postgresql_where=text("status IN ('queued', 'running')"),
        ),
    )


class ExerciseProgress(Base):
    """Per-learner state for an exercise, keyed by stable id so passes survive new versions."""

    __tablename__ = "exercise_progress"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    exercise_id: Mapped[str] = mapped_column(String(130), primary_key=True)
    hints_revealed: Mapped[int] = mapped_column(Integer, default=0)
    first_passed_at: Mapped[datetime | None] = mapped_column()
    passing_attempt_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("attempts.id"))


class Draft(Base):
    """Autosaved work in progress, so a refresh never loses code."""

    __tablename__ = "drafts"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    exercise_id: Mapped[str] = mapped_column(String(130), primary_key=True)
    files: Mapped[dict[str, Any]] = mapped_column()
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)


class XpEvent(Base):
    """Append-only XP ledger. Totals and levels are always derived from it."""

    __tablename__ = "xp_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    exercise_id: Mapped[str | None] = mapped_column(String(130))
    reason: Mapped[str] = mapped_column(String(32))
    amount: Mapped[int] = mapped_column(Integer)
    attempt_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("attempts.id"))
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    __table_args__ = (
        UniqueConstraint("user_id", "exercise_id", "reason", name="uq_xp_once_per_reason"),
        CheckConstraint("amount > 0", name="amount_positive"),
        Index("ix_xp_events_user", "user_id"),
    )


class TalentAllocation(Base):
    """A talent a learner has taken. Points are derived from level, never stored."""

    __tablename__ = "talent_allocations"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    node_id: Mapped[str] = mapped_column(String(64))
    allocated_at: Mapped[datetime] = mapped_column(default=utcnow)

    __table_args__ = (UniqueConstraint("user_id", "node_id", name="uq_talent_once"),)


class BadgeAward(Base):
    """Append-only badge awards, with the attempt that earned each. Never revoked."""

    __tablename__ = "badge_awards"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    badge_id: Mapped[str] = mapped_column(String(64))
    attempt_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("attempts.id"))
    awarded_at: Mapped[datetime] = mapped_column(default=utcnow)

    __table_args__ = (UniqueConstraint("user_id", "badge_id", name="uq_badge_once"),)


class Certificate(Base):
    """Proof that a learner completed a branch. Snapshots what it attests; never revoked.

    The id is the public credential id: random and unguessable, so a private certificate cannot
    be found and a public one cannot be enumerated. `branch_id` has no foreign key on purpose:
    the certificate outlives any change to content.
    """

    __tablename__ = "certificates"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_public_id)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    branch_id: Mapped[str] = mapped_column(String(64))
    recipient_name: Mapped[str] = mapped_column(String(60))  # editable by the owner
    branch_title: Mapped[str] = mapped_column(String(80))
    exercise_count: Mapped[int] = mapped_column(Integer)
    # Whether the branch had a capstone when this was issued; false for older certificates, which
    # never claim one.
    includes_capstone: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    issued_at: Mapped[datetime] = mapped_column(default=utcnow)
    # The attempt whose pass completed the branch; null for certificates backfilled later.
    attempt_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("attempts.id"))
    is_public: Mapped[bool] = mapped_column(Boolean, default=False)
    published_at: Mapped[datetime | None] = mapped_column()

    __table_args__ = (
        UniqueConstraint("user_id", "branch_id", name="uq_certificate_once"),
        CheckConstraint("exercise_count > 0", name="exercise_count_positive"),
    )


class WorkerHeartbeat(Base):
    """When each grading worker process last polled the queue. Read by the ops status probe.

    One row per worker process (its id changes on every start); the worker deletes rows that
    have been silent for a day, so the table stays a handful of rows.
    """

    __tablename__ = "worker_heartbeats"

    worker_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    started_at: Mapped[datetime] = mapped_column(default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(default=utcnow)


class LiveRun(Base):
    """An in-app live run (ADR 0012): the learner's files run with `live.py` against the
    platform's model. The row doubles as the job, claimed by the grading worker like an attempt.

    It is never retried: a run spends real money, so one the worker lost is `errored`, not
    re-queued. `result` holds the program's bounded output and each call's cost and latency.
    """

    __tablename__ = "live_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    exercise_id: Mapped[str] = mapped_column(String(130))
    files: Mapped[dict[str, Any]] = mapped_column()
    status: Mapped[str] = mapped_column(String(16), default="queued")
    result: Mapped[dict[str, Any] | None] = mapped_column()
    worker_id: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    claimed_at: Mapped[datetime | None] = mapped_column()
    finished_at: Mapped[datetime | None] = mapped_column()

    __table_args__ = (
        CheckConstraint(
            "status IN ('queued', 'running', 'finished', 'errored')", name="live_run_status_valid"
        ),
        Index("ix_live_runs_user_created", "user_id", "created_at"),
        Index("ix_live_runs_queue", "created_at", postgresql_where=text("status = 'queued'")),
        # At most one live run in flight per learner.
        Index(
            "uq_live_runs_in_flight",
            "user_id",
            unique=True,
            postgresql_where=text("status IN ('queued', 'running')"),
        ),
    )


class LiveCall(Base):
    """One model call the live-run proxy made for a learner, with what it cost. Spending caps
    are summed from these rows, so they are the record the caps are enforced from."""

    __tablename__ = "live_calls"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("live_runs.id", ondelete="SET NULL")
    )
    exercise_id: Mapped[str] = mapped_column(String(130))
    model: Mapped[str] = mapped_column(String(64))
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cache_read_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cache_write_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(14, 8), default=Decimal(0))
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    # "ok", or the provider's error kind ("rate_limit", "server", "invalid"), billed nothing.
    outcome: Mapped[str] = mapped_column(String(16), default="ok")
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    __table_args__ = (
        Index("ix_live_calls_user_created", "user_id", "created_at"),
        Index("ix_live_calls_created", "created_at"),  # for the 13-month retention purge
    )


class Subscription(Base):
    """A learner's Stripe customer and the mirror of their subscription (docs/plans/billing.md).

    One row per learner, created when they first open Checkout. Stripe is the source of truth:
    every webhook re-fetches the subscription and overwrites these fields, and `users.plan` is
    derived from them (`lattice.domain.billing.plan_for`).
    """

    __tablename__ = "subscriptions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    stripe_customer_id: Mapped[str] = mapped_column(String(255), unique=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(255), unique=True)
    status: Mapped[str | None] = mapped_column(String(24))
    interval: Mapped[str | None] = mapped_column(String(8))  # "monthly" or "annual"
    price_id: Mapped[str | None] = mapped_column(String(255))
    started_at: Mapped[datetime | None] = mapped_column()
    trial_end: Mapped[datetime | None] = mapped_column()
    current_period_end: Mapped[datetime | None] = mapped_column()
    cancel_at_period_end: Mapped[bool] = mapped_column(Boolean, default=False)
    cancel_at: Mapped[datetime | None] = mapped_column()
    paused: Mapped[bool] = mapped_column(Boolean, default=False)
    resumes_at: Mapped[datetime | None] = mapped_column()
    latest_invoice_id: Mapped[str | None] = mapped_column(String(255))
    # The billing address's country (ISO 3166-1 alpha-2), for the EU withdrawal control.
    country: Mapped[str | None] = mapped_column(String(2))
    # Set once a subscription has existed: a returning learner gets no second free trial.
    trial_used: Mapped[bool] = mapped_column(Boolean, default=False)
    # When the day-3 onboarding nudge went, so it goes once.
    onboarding_nudged_at: Mapped[datetime | None] = mapped_column()
    # Set when a withdrawal was refunded but Stripe would not cancel: the owner cancels by hand.
    withdrawal_cancel_failed_at: Mapped[datetime | None] = mapped_column()
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)


class BillingEvent(Base):
    """A Stripe webhook event already processed. Recording the id in the same transaction as its
    effects makes processing idempotent: a redelivery finds the row and does nothing."""

    __tablename__ = "billing_events"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)  # evt_…
    type: Mapped[str] = mapped_column(String(64))
    received_at: Mapped[datetime] = mapped_column(default=utcnow)


class BillingConsent(Base):
    """A learner's regulation-37 consent, recorded before Checkout opens: when, which wording
    (by version, and the words themselves) and for which plan.

    It is the evidence of the waiver, so it outlives the account: deleting the account copies the
    Stripe ids here and clears `user_id`, leaving no email or name. Kept six years (`retention`).
    """

    __tablename__ = "billing_consents"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    wording_version: Mapped[str] = mapped_column(String(32))
    wording: Mapped[str] = mapped_column(Text)
    plan: Mapped[str] = mapped_column(String(8))
    checkout_session_id: Mapped[str | None] = mapped_column(String(255))
    # Filled when the account is deleted, so the pseudonymised record still ties to Stripe's.
    stripe_customer_id: Mapped[str | None] = mapped_column(String(255))
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(255))

    __table_args__ = (
        CheckConstraint("plan IN ('monthly', 'annual')", name="consent_plan_valid"),
        Index("ix_billing_consents_user", "user_id", "created_at"),
        Index("ix_billing_consents_session", "checkout_session_id"),
    )


class LiveNoticeAcknowledgement(Base):
    """A learner acknowledging the live-run data notice (who receives what, and for how long)
    before their first live run. `version` names the wording they saw; a new wording asks again."""

    __tablename__ = "live_notice_acknowledgements"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    version: Mapped[str] = mapped_column(String(32))
    acknowledged_at: Mapped[datetime] = mapped_column(default=utcnow)

    __table_args__ = (
        UniqueConstraint("user_id", "version", name="uq_live_notice_once_per_version"),
    )
