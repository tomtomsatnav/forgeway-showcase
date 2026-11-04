"""Paid subscriptions through Stripe (docs/plans/billing.md): Checkout, the Customer Portal, our
own pause, EU withdrawal, webhooks, a daily reconciliation and the day-3 onboarding nudge.

Stripe is the source of truth. A webhook never trusts the event's copy of an object: it records
the event id (idempotency), re-fetches the subscription from the API and overwrites the mirror in
`subscriptions`, so events arriving twice or out of order converge on Stripe's current state.
`users.plan` is derived from the mirror (`domain.billing.plan_for`); entitlements read it as
before. With billing off none of this runs, and the waitlist stays as it was.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from threading import Lock

from sqlalchemy import exists, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from lattice.application import billing_emails as emails
from lattice.application.errors import (
    BillingUnavailableError,
    ConflictError,
    ConsentRequiredError,
    NotFoundError,
)
from lattice.domain.billing import (
    CONSENT_ACKNOWLEDGEMENT,
    CONSENT_EXPRESS,
    CONSENT_VERSION,
    LIVE_STATUSES,
    WITHDRAWAL_PERIOD,
    BillingEvent,
    BillingGateway,
    CheckoutRequest,
    Interval,
    SubscriptionSnapshot,
    first_charge_date,
    plan_for,
    renewal_cooling_off_deadline,
    withdrawal_deadline,
)
from lattice.domain.email import EmailMessage
from lattice.domain.entitlements import Plan
from lattice.infrastructure.db.models import (
    BillingConsent,
    ExerciseProgress,
    LearnerProfile,
    LiveRun,
    Subscription,
    User,
)
from lattice.infrastructure.db.models import BillingEvent as BillingEventRow

logger = logging.getLogger(__name__)

CONSENT_WORDING = f"{CONSENT_EXPRESS} {CONSENT_ACKNOWLEDGEMENT}"
NUDGE_AFTER = timedelta(days=3)
PAUSE_MONTH = timedelta(days=30)
SUBSCRIPTION_EVENTS = frozenset(
    {
        "customer.subscription.created",
        "customer.subscription.updated",
        "customer.subscription.deleted",
        "customer.subscription.paused",
        "customer.subscription.resumed",
    }
)


@dataclass
class Billing:
    """Billing as configured: the gateway, the two prices and the trial. Built only when on."""

    gateway: BillingGateway
    price_ids: dict[Interval, str]
    amounts: dict[Interval, int]  # pence, VAT included: what the site shows
    trial_days: int
    base_url: str
    _prices_ok: bool = field(default=False, init=False)
    _lock: Lock = field(default_factory=Lock, init=False)

    @property
    def links(self) -> emails.Links:
        return emails.Links(self.base_url)

    def interval_of(self, price_id: str | None) -> Interval | None:
        return next((i for i, p in self.price_ids.items() if p == price_id), None)

    def price_problems(self) -> list[str]:
        """Where the configured prices differ from Stripe's. Empty when they agree."""
        problems = []
        expected = {"monthly": "month", "annual": "year"}
        for interval, price_id in self.price_ids.items():
            price = self.gateway.price(price_id)
            if price.unit_amount != self.amounts[interval]:
                problems.append(
                    f"{interval} price {price_id} is {price.unit_amount} in Stripe but the site "
                    f"shows {self.amounts[interval]}"
                )
            if price.currency.lower() != "gbp":
                problems.append(f"{interval} price {price_id} is in {price.currency}, not GBP")
            if price.tax_behavior != "inclusive":
                problems.append(f"{interval} price {price_id} is not tax-inclusive")
            if price.interval != expected[interval]:
                problems.append(f"{interval} price {price_id} recurs every {price.interval}")
            if not price.active:
                problems.append(f"{interval} price {price_id} is archived")
        return problems

    def ensure_prices(self) -> None:
        """Check the prices against Stripe once per process, before the first Checkout. A
        mismatch refuses Checkout, so nobody is charged a price the site did not show."""
        with self._lock:
            if self._prices_ok:
                return
            problems = self.price_problems()
            if problems:
                for problem in problems:
                    logger.error("BILLING PRICE MISMATCH: %s", problem)
                raise BillingUnavailableError(
                    "Subscriptions are unavailable for a moment. Please try again later."
                )
            self._prices_ok = True


# --- What the learner sees -------------------------------------------------------------------


@dataclass(frozen=True)
class SubscriptionView:
    status: str
    interval: Interval | None
    paused: bool
    resumes_at: datetime | None
    trial_end: datetime | None
    current_period_end: datetime | None
    cancelling: bool
    ends_at: datetime | None  # when a cancelled subscription stops, if it is cancelling
    # EU customers within 14 days of the contract; from 2027, anyone in a renewal cooling-off.
    withdrawal_until: datetime | None


@dataclass(frozen=True)
class BillingView:
    enabled: bool
    plan: Plan
    trial_days: int  # the trial this learner would get now; 0 after a first subscription
    subscription: SubscriptionView | None


def view(session: Session, billing: Billing | None, user: User) -> BillingView:
    plan = Plan(user.plan)
    if billing is None:
        return BillingView(enabled=False, plan=plan, trial_days=0, subscription=None)
    row = session.get(Subscription, user.id)
    trial_days = 0 if row is not None and row.trial_used else billing.trial_days
    if row is None or row.status is None or row.stripe_subscription_id is None:
        return BillingView(enabled=True, plan=plan, trial_days=trial_days, subscription=None)
    return BillingView(
        enabled=True,
        plan=plan,
        trial_days=trial_days,
        subscription=SubscriptionView(
            status=row.status,
            interval=_interval(row),
            paused=row.paused,
            resumes_at=row.resumes_at,
            trial_end=row.trial_end if row.status == "trialing" else None,
            current_period_end=row.current_period_end,
            cancelling=_cancelling(row),
            ends_at=(row.cancel_at or row.current_period_end) if _cancelling(row) else None,
            withdrawal_until=_withdrawal_until(row),
        ),
    )


def _cancelling(row: Subscription) -> bool:
    return row.status in LIVE_STATUSES and (row.cancel_at_period_end or row.cancel_at is not None)


def _withdrawal_until(row: Subscription, now: datetime | None = None) -> datetime | None:
    """Until when the learner may withdraw with a refund: the EU right to withdraw, or the
    renewal cooling-off period (trial conversion and annual renewal, from 2027)."""
    return max(_withdrawal_deadlines(row, now), default=None)


def _withdrawal_opened(row: Subscription, now: datetime | None = None) -> datetime | None:
    """When the earliest withdrawal period still open began: each lasts 14 days."""
    deadlines = _withdrawal_deadlines(row, now)
    return min(deadlines) - WITHDRAWAL_PERIOD if deadlines else None


def _withdrawal_deadlines(row: Subscription, now: datetime | None = None) -> list[datetime]:
    if row.status not in LIVE_STATUSES or row.started_at is None:
        return []
    now = now or datetime.now(UTC)
    eu = withdrawal_deadline(row.started_at, row.country)
    renewal = (
        None
        if row.status == "trialing"
        else renewal_cooling_off_deadline(
            started_at=row.started_at,
            trial_end=row.trial_end,
            interval=_interval(row),
            current_period_end=row.current_period_end,
            now=now,
        )
    )
    return [d for d in (eu, renewal) if d is not None and d > now]


# --- Checkout, portal, pause, withdrawal -----------------------------------------------------


def start_checkout(
    session: Session,
    billing: Billing,
    user: User,
    interval: Interval,
    *,
    consent: bool,
    consent_version: str,
    marketing_opt_out: bool = False,
    now: datetime | None = None,
) -> str:
    """Record the regulation-37 consent, then open a Checkout Session. Returns its URL.

    The consent must be given, in the wording currently shown, before anything else happens.
    A ticked "no offers" box (`marketing_opt_out`) opts the learner out of marketing email."""
    if not consent or consent_version != CONSENT_VERSION:
        raise ConsentRequiredError(
            "Tick the box to agree that Pro starts straight away, then try again."
        )
    row = session.get(Subscription, user.id, with_for_update=True)
    if row is not None and row.status in LIVE_STATUSES:
        raise ConflictError("You already have Forgeway Pro. Manage it from your profile.")
    billing.ensure_prices()
    if marketing_opt_out:
        profile = session.get(LearnerProfile, user.id)
        if profile is not None:
            profile.marketing_opt_out = True
    if row is None:
        customer = billing.gateway.create_customer(str(user.id), user.email, user.display_name)
        # Two tabs racing to their first Checkout: the second insert does nothing (it waits for
        # the first to commit) and both carry on with the one row.
        session.execute(
            insert(Subscription)
            .values(user_id=user.id, stripe_customer_id=customer, trial_used=False)
            .on_conflict_do_nothing()
        )
        row = session.get(Subscription, user.id, with_for_update=True)
        assert row is not None  # noqa: S101 - inserted above, or by the racing request
    trial_days = 0 if row.trial_used else billing.trial_days
    amount = billing.amounts[interval]
    record = BillingConsent(
        user_id=user.id,
        created_at=now or datetime.now(UTC),
        wording_version=CONSENT_VERSION,
        wording=CONSENT_WORDING,
        plan=interval,
    )
    session.add(record)
    session.flush()
    session_id, url = billing.gateway.create_checkout(
        CheckoutRequest(
            user_id=str(user.id),
            customer_id=row.stripe_customer_id,
            price_id=billing.price_ids[interval],
            trial_days=trial_days,
            success_url=f"{billing.links.at('/pro/success')}?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=billing.links.at("/pro/cancelled"),
            submit_message=submit_message(interval, amount, trial_days, now),
        )
    )
    record.checkout_session_id = session_id
    return url


def submit_message(
    interval: Interval, amount: int, trial_days: int, now: datetime | None = None
) -> str:
    """Beside Checkout's pay button: exactly what the learner is agreeing to pay, and when."""
    period = emails.PERIOD[interval]
    if trial_days <= 0:
        return (
            f"You will be charged {emails.price(amount)} today and every {period} until you "
            "cancel. Cancel any time from your Forgeway profile."
        )
    first = first_charge_date((now or datetime.now(UTC)).date(), trial_days)
    return (
        f"Nothing is charged today. Your {trial_days}-day free trial starts now; unless you cancel "
        f"before it ends, you will be charged {emails.price(amount)} on {emails.day(first)} and "
        f"every {period} after that until you cancel."
    )


def portal_url(session: Session, billing: Billing, user: User) -> str:
    row = session.get(Subscription, user.id)
    if row is None:
        raise NotFoundError("There is no subscription to manage yet.")
    return billing.gateway.create_portal(row.stripe_customer_id, billing.links.billing)


def pause(session: Session, billing: Billing, user: User, months: int) -> None:
    """Pause collection for 1 to 3 months (the portal has no pause). Pro pauses with it."""
    row = _live_row(session, user)
    if row.status != "active":
        raise ConflictError(
            "A subscription can be paused once its trial is over and its payments are up to date."
        )
    if row.paused:
        raise ConflictError("Your subscription is already paused.")
    resumes_at = datetime.now(UTC) + PAUSE_MONTH * max(1, min(months, 3))
    _apply(session, billing, billing.gateway.pause(_sub_id(row), resumes_at))


def resume(session: Session, billing: Billing, user: User) -> None:
    row = _live_row(session, user)
    if not row.paused:
        raise ConflictError("Your subscription is not paused.")
    _apply(session, billing, billing.gateway.resume(_sub_id(row)))


def withdraw(session: Session, billing: Billing, user: User) -> EmailMessage:
    """The "Withdraw from contract" control: refund what was paid in the period, then end the
    contract now.

    For EU customers within 14 days of the contract (Directive 2023/2673), and from 2027 for
    anyone within 14 days of a trial converting or an annual renewal (the DMCC renewal
    cooling-off, which cannot be waived). The refund is in full, never less than the law asks."""
    row = _live_row(session, user)
    opened = _withdrawal_opened(row)
    if opened is None:
        raise ConflictError(
            "The 14-day withdrawal period has ended. You can still cancel from Manage billing."
        )
    sub_id = _sub_id(row)
    # Refund first, then cancel: a cancelled contract whose refund failed would leave the
    # learner without Pro and without their money. Every payment since the period opened is
    # refunded, not only the latest invoice (after a plan switch that is just the proration).
    refunded = 0
    try:
        for invoice in billing.gateway.paid_invoices(sub_id, opened):
            if invoice.amount_paid > 0:
                billing.gateway.refund_invoice(invoice.id, invoice.amount_paid)
                refunded += invoice.amount_paid
    except Exception as err:
        logger.exception("billing withdrawal: refund failed", extra={"user_id": str(user.id)})
        raise BillingUnavailableError(
            "We could not refund your payment just now, so your subscription has not been "
            "cancelled. Please try again in a few minutes."
        ) from err
    try:
        snapshot = billing.gateway.cancel_now(sub_id)
    except Exception:
        # Refunded but still subscribed: recorded, and logged for the owner to cancel in Stripe.
        logger.exception(
            "BILLING WITHDRAWAL NOT CANCELLED: refunded, but the subscription is still live; "
            "cancel it in Stripe",
            extra={"user_id": str(user.id), "subscription": sub_id, "refunded": refunded},
        )
        row.withdrawal_cancel_failed_at = datetime.now(UTC)
        return emails.withdrawal_processing(
            _recipient(session, user), billing.links, refunded=refunded
        )
    row.withdrawal_cancel_failed_at = None
    _apply(session, billing, snapshot)
    logger.info("billing withdrawal", extra={"user_id": str(user.id), "refunded": refunded})
    return emails.withdrawal_confirmed(_recipient(session, user), billing.links, refunded=refunded)


def live_subscription_id(session: Session, user: User) -> str | None:
    """The learner's live Stripe subscription, if any: read before deleting the account."""
    row = session.get(Subscription, user.id)
    return row.stripe_subscription_id if row is not None and row.status in LIVE_STATUSES else None


def cancel_for_deletion(billing: Billing | None, subscription_id: str | None) -> None:
    """End a deleted account's subscription at once, so nobody is billed for an account that no
    longer exists. Called after the account's rows are committed away: the deletion stands even
    if Stripe fails, and the failure is logged for the owner to cancel by hand (the id is kept on
    the pseudonymised consent record)."""
    if billing is None or subscription_id is None:
        return
    try:
        billing.gateway.cancel_now(subscription_id)
    except Exception:
        logger.exception(
            "BILLING DELETION NOT CANCELLED: the account is deleted but its subscription is "
            "still live; cancel it in Stripe",
            extra={"subscription": subscription_id},
        )


def _live_row(session: Session, user: User) -> Subscription:
    row = session.get(Subscription, user.id, with_for_update=True)
    if row is None or row.status not in LIVE_STATUSES or row.stripe_subscription_id is None:
        raise NotFoundError("You have no active subscription.")
    return row


def _sub_id(row: Subscription) -> str:
    assert row.stripe_subscription_id is not None  # noqa: S101 - checked by the callers
    return row.stripe_subscription_id


# --- Webhooks --------------------------------------------------------------------------------


def handle_event(session: Session, billing: Billing, event: BillingEvent) -> list[EmailMessage]:
    """Process one verified event, once. Returns the emails to send after the commit.

    The event id is recorded in the same transaction as its effects: if anything fails, both
    roll back and Stripe's redelivery tries again; a second delivery of a processed event finds
    the id and does nothing."""
    recorded = session.execute(
        insert(BillingEventRow)
        .values(id=event.id, type=event.type, received_at=datetime.now(UTC))
        .on_conflict_do_nothing(index_elements=[BillingEventRow.id])
        .returning(BillingEventRow.id)
    ).first()
    if recorded is None:
        logger.info("billing event already processed", extra={"event_id": event.id})
        return []
    kind = event.type
    if kind == "checkout.session.completed" and event.object_id:
        return _checkout_completed(session, billing, event.object_id)
    if kind in SUBSCRIPTION_EVENTS and event.object_id:
        return _subscription_changed(session, billing, event.object_id)
    if kind == "customer.subscription.trial_will_end" and event.object_id:
        return _trial_will_end(session, billing, event.object_id)
    if kind in ("invoice.paid", "invoice.payment_failed") and event.object_id:
        invoice = billing.gateway.invoice(event.object_id)
        if invoice.subscription_id is None:
            return []
        row = _sync(session, billing, invoice.subscription_id)
        if kind == "invoice.paid" or row is None:
            return []
        interval = _interval(row)
        return [
            emails.payment_failed(
                _recipient(session, _user(session, row)),
                billing.links,
                amount=billing.amounts[interval] if interval else None,
                update_url=invoice.hosted_invoice_url,
            )
        ]
    if kind == "invoice.upcoming" and event.subscription_id:
        return _upcoming(session, billing, event.subscription_id)
    if kind in ("charge.dispute.created", "charge.refunded"):
        # Disputes and refunds made in the dashboard: the owner acts on them in Stripe. Any
        # effect on the subscription arrives as its own customer.subscription.* event.
        logger.warning("billing %s", kind, extra={"customer": event.customer_id})
        return []
    logger.info("billing event ignored", extra={"event_type": kind})
    return []


def _checkout_completed(session: Session, billing: Billing, session_id: str) -> list[EmailMessage]:
    checkout = billing.gateway.checkout_session(session_id)
    if checkout.subscription_id is None or checkout.customer_id is None:
        return []
    row = session.scalars(
        select(Subscription)
        .where(Subscription.stripe_customer_id == checkout.customer_id)
        .with_for_update()
    ).first()
    if row is not None and checkout.country:
        row.country = checkout.country.upper()[:2]
    row = _sync(session, billing, checkout.subscription_id)
    if row is None:
        return []
    consent = session.scalars(
        select(BillingConsent).where(BillingConsent.checkout_session_id == session_id)
    ).first()
    user = _user(session, row)
    interval = _interval(row)
    if interval is None:
        return []
    trial_days = (
        round((row.trial_end - row.started_at).total_seconds() / 86400)
        if row.trial_end is not None and row.started_at is not None
        else 0
    )
    return [
        emails.confirmation(
            _recipient(session, user),
            billing.links,
            interval=interval,
            amount=billing.amounts[interval],
            trial_days=trial_days,
            trial_end=row.trial_end if row.status == "trialing" else None,
            consent_at=consent.created_at if consent else None,
            consent_wording=consent.wording if consent else None,
        )
    ]


def _subscription_changed(
    session: Session, billing: Billing, subscription_id: str
) -> list[EmailMessage]:
    before = session.scalars(
        select(Subscription).where(Subscription.stripe_subscription_id == subscription_id)
    ).first()
    was_live = before is not None and before.status in LIVE_STATUSES
    was_cancelling = before is not None and _cancelling(before)
    row = _sync(session, billing, subscription_id)
    if row is None or row.stripe_subscription_id != subscription_id:
        return []
    # The end-of-contract confirmation, once, when a live subscription is cancelled: at the end
    # of the period (portal) or at once (dashboard).
    ended = _cancelling(row) or row.status == "canceled"
    if not (was_live and not was_cancelling and ended):
        return []
    ends_at = (row.cancel_at or row.current_period_end) if _cancelling(row) else None
    return [
        emails.cancellation_confirmed(
            _recipient(session, _user(session, row)), billing.links, ends_at=ends_at
        )
    ]


def _trial_will_end(session: Session, billing: Billing, subscription_id: str) -> list[EmailMessage]:
    row = _sync(session, billing, subscription_id)
    interval = _interval(row) if row is not None else None
    if row is None or row.status != "trialing" or row.trial_end is None or interval is None:
        return []
    if _cancelling(row):
        return []  # they have already cancelled; nothing will be charged
    return [
        emails.trial_ending(
            _recipient(session, _user(session, row)),
            billing.links,
            interval=interval,
            amount=billing.amounts[interval],
            trial_end=row.trial_end,
        )
    ]


def _upcoming(session: Session, billing: Billing, subscription_id: str) -> list[EmailMessage]:
    row = _sync(session, billing, subscription_id)
    if (
        row is None
        or row.interval != "annual"
        or row.status != "active"
        or _cancelling(row)
        or row.current_period_end is None
    ):
        return []
    return [
        emails.renewal_reminder(
            _recipient(session, _user(session, row)),
            billing.links,
            amount=billing.amounts["annual"],
            renews_at=row.current_period_end,
        )
    ]


def _sync(session: Session, billing: Billing, subscription_id: str) -> Subscription | None:
    """Re-fetch the subscription from Stripe and write it to the mirror and the plan.

    The learner's row is locked before the fetch, so two deliveries for one learner cannot
    write an older state over a newer one. On a subscription's first event the row does not
    name it yet: the customer's row is locked and the subscription fetched again under the lock,
    so a concurrent delivery's earlier copy cannot land after this one."""
    row = session.scalars(
        select(Subscription)
        .where(Subscription.stripe_subscription_id == subscription_id)
        .with_for_update()
    ).first()
    snapshot = billing.gateway.subscription(subscription_id)
    if row is None:
        row = session.scalars(
            select(Subscription)
            .where(Subscription.stripe_customer_id == snapshot.customer_id)
            .with_for_update()
        ).first()
        if row is not None:
            snapshot = billing.gateway.subscription(subscription_id)
    return _apply(session, billing, snapshot, row)


def _apply(
    session: Session,
    billing: Billing,
    snapshot: SubscriptionSnapshot,
    row: Subscription | None = None,
) -> Subscription | None:
    row = (
        row
        or session.scalars(
            select(Subscription)
            .where(Subscription.stripe_customer_id == snapshot.customer_id)
            .with_for_update()
        ).first()
    )
    user_id = _uuid(snapshot.user_id)
    if row is None and user_id is not None:
        row = session.get(Subscription, user_id, with_for_update=True)
    if row is None:
        logger.warning(
            "billing: subscription for an unknown customer",
            extra={"subscription": snapshot.id, "customer": snapshot.customer_id},
        )
        return None
    if (
        row.stripe_subscription_id not in (None, snapshot.id)
        and row.status in LIVE_STATUSES
        and snapshot.status not in LIVE_STATUSES
    ):
        # A late event about an older, ended subscription: the live one stands.
        return row
    row.stripe_subscription_id = snapshot.id
    row.status = snapshot.status
    row.price_id = snapshot.price_id
    row.interval = billing.interval_of(snapshot.price_id) or snapshot.interval
    row.started_at = snapshot.started_at
    row.trial_end = snapshot.trial_end
    row.current_period_end = snapshot.current_period_end
    row.cancel_at_period_end = snapshot.cancel_at_period_end
    row.cancel_at = snapshot.cancel_at
    row.paused = snapshot.paused
    row.resumes_at = snapshot.resumes_at
    row.latest_invoice_id = snapshot.latest_invoice_id
    row.trial_used = True
    user = _user(session, row)
    if user.plan != Plan.TEAM:  # Team is granted by hand; billing only moves free and pro
        user.plan = plan_for(snapshot.status, paused=snapshot.paused).value
    session.flush()
    return row


# --- Reconciliation --------------------------------------------------------------------------


def subscriptions_to_reconcile(session: Session, now: datetime | None = None) -> list[str]:
    """Every subscription the mirror holds as live, so a lost webhook cannot leave anyone on the
    wrong plan for long. A trial whose end has passed is always among them, whatever status set
    counts as live: Stripe has moved it on, and the mirror has not heard."""
    now = now or datetime.now(UTC)
    rows = session.scalars(
        select(Subscription.stripe_subscription_id)
        .where(
            Subscription.stripe_subscription_id.is_not(None),
            or_(
                Subscription.status.in_(LIVE_STATUSES),
                (Subscription.status == "trialing") & (Subscription.trial_end < now),
            ),
        )
        .order_by(Subscription.user_id)
    )
    return [subscription_id for subscription_id in rows if subscription_id is not None]


def reconcile(session: Session, billing: Billing, subscription_id: str) -> list[EmailMessage]:
    """Re-fetch one subscription and re-apply it, as its webhook would have."""
    return _subscription_changed(session, billing, subscription_id)


def failed_withdrawal_cancels(session: Session) -> list[str]:
    """Subscriptions refunded by a withdrawal whose cancellation Stripe then refused."""
    rows = session.scalars(
        select(Subscription.stripe_subscription_id)
        .where(
            Subscription.withdrawal_cancel_failed_at.is_not(None),
            Subscription.stripe_subscription_id.is_not(None),
        )
        .order_by(Subscription.user_id)
    )
    return [subscription_id for subscription_id in rows if subscription_id is not None]


def retry_withdrawal_cancel(
    session: Session, billing: Billing, subscription_id: str
) -> list[EmailMessage]:
    """Finish a withdrawal: cancel at Stripe and clear the record, with the email the learner was
    promised. One already ended (the owner cancelled it by hand) only needs recording. A failure
    is logged at ERROR and raised, and the record stays for the next run."""
    row = session.scalars(
        select(Subscription)
        .where(Subscription.stripe_subscription_id == subscription_id)
        .with_for_update()
    ).one()
    try:
        snapshot = billing.gateway.subscription(subscription_id)
        if snapshot.status in LIVE_STATUSES:
            snapshot = billing.gateway.cancel_now(subscription_id)
    except Exception:
        logger.exception(
            "BILLING WITHDRAWAL NOT CANCELLED: refunded, but the subscription is still live; "
            "cancel it in Stripe",
            extra={"subscription": subscription_id},
        )
        raise
    row.withdrawal_cancel_failed_at = None
    _apply(session, billing, snapshot, row)
    return [
        emails.cancellation_confirmed(
            _recipient(session, _user(session, row)), billing.links, ends_at=None
        )
    ]


# --- Onboarding ------------------------------------------------------------------------------


@dataclass(frozen=True)
class Onboarding:
    """The first-week milestones since a trial started."""

    first_pass_at: datetime | None
    first_live_run_at: datetime | None

    @property
    def started(self) -> bool:
        return self.first_pass_at is not None or self.first_live_run_at is not None


def onboarding(session: Session, user_id: uuid.UUID, since: datetime) -> Onboarding:
    """First exercise passed and first live run since `since`. Live runs are read from
    `live_runs` (ADR 0012): the hook is here, so nothing in the worker needs to know."""
    first_pass = session.scalar(
        select(ExerciseProgress.first_passed_at)
        .where(ExerciseProgress.user_id == user_id, ExerciseProgress.first_passed_at >= since)
        .order_by(ExerciseProgress.first_passed_at)
        .limit(1)
    )
    first_live = session.scalar(
        select(LiveRun.finished_at)
        .where(
            LiveRun.user_id == user_id,
            LiveRun.status == "finished",
            LiveRun.finished_at >= since,
        )
        .order_by(LiveRun.finished_at)
        .limit(1)
    )
    return Onboarding(first_pass, first_live)


def onboarding_nudges(
    session: Session, base_url: str, now: datetime | None = None
) -> list[EmailMessage]:
    """The day-3 nudge for every trial three or more days old with no exercise passed and no
    live run since it started. Each learner is nudged at most once. Run daily."""
    now = now or datetime.now(UTC)
    rows = session.scalars(
        select(Subscription)
        .where(
            Subscription.status == "trialing",
            Subscription.onboarding_nudged_at.is_(None),
            Subscription.started_at <= now - NUDGE_AFTER,
            ~exists().where(
                ExerciseProgress.user_id == Subscription.user_id,
                ExerciseProgress.first_passed_at >= Subscription.started_at,
            ),
        )
        .with_for_update(skip_locked=True)
    ).all()
    messages = []
    for row in rows:
        assert row.started_at is not None  # noqa: S101 - filtered above
        if onboarding(session, row.user_id, row.started_at).started:
            continue
        row.onboarding_nudged_at = now
        messages.append(
            emails.onboarding_nudge(
                _recipient(session, _user(session, row)),
                emails.Links(base_url),
                trial_end=row.trial_end,
            )
        )
    return messages


# --- Helpers ---------------------------------------------------------------------------------


def _user(session: Session, row: Subscription) -> User:
    user = session.get(User, row.user_id)
    assert user is not None  # noqa: S101 - the row cascades with the user
    return user


def _recipient(session: Session, user: User) -> emails.Recipient:
    profile = session.get(LearnerProfile, user.id)
    return emails.Recipient(user.email, user.display_name, profile.time_zone if profile else "UTC")


def _uuid(value: str | None) -> uuid.UUID | None:
    try:
        return uuid.UUID(value) if value else None
    except ValueError:
        return None


def _interval(row: Subscription) -> Interval | None:
    return "annual" if row.interval == "annual" else "monthly" if row.interval else None
