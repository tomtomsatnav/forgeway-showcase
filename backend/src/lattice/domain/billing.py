"""Subscriptions: how a payment processor's subscription maps to a plan, and the port to it.

The processor (Stripe, docs/plans/billing.md) is the source of truth for a subscription. Forgeway
keeps a mirror of the fields it needs and derives the learner's `Plan` from the status alone:

- `trialing` and `active` grant Pro;
- `past_due` keeps Pro while the processor retries the card, and the app shows a banner;
- `canceled`, `unpaid`, `paused`, `incomplete` and `incomplete_expired` return the learner to
  Free, and so does a paused collection (our own pause screen), whatever the status says.

The regulation-37 consent wording lives here too: the browser shows it from the API, the
consent record stores its version, and the confirmation email repeats it, so all three agree.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Literal, Protocol

from lattice.domain.entitlements import Plan

Interval = Literal["monthly", "annual"]

PRO_STATUSES = frozenset({"trialing", "active", "past_due"})
FREE_STATUSES = frozenset({"canceled", "unpaid", "paused", "incomplete", "incomplete_expired"})
# A subscription in one of these is still a contract the learner can pause, cancel or withdraw from.
LIVE_STATUSES = PRO_STATUSES

# The EU right to withdraw lasts 14 days from the contract (Directive 2011/83/EU, art. 9).
WITHDRAWAL_PERIOD = timedelta(days=14)
EU_COUNTRIES = frozenset(
    {
        "AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR", "GR", "DE", "HU", "IE",
        "IT", "LV", "LT", "LU", "MT", "NL", "PL", "PT", "RO", "SK", "SI", "ES", "SE",
    }
)  # fmt: skip

# The DMCC Act 2024 subscription regime (from 1 January 2027, if Parliament approves the draft
# regulations): a 14-day renewal cooling-off period, which cannot be waived, after a free trial
# converts to paid and after each renewal of a contract of 12 months or more.
RENEWAL_COOLING_OFF_FROM = datetime(2027, 1, 1, tzinfo=UTC)
RENEWAL_COOLING_OFF = timedelta(days=14)

# Regulation 37 (CCRs 2013): express consent to start straight away, and the acknowledgement that
# the right to cancel is then lost. Change the words, change the version.
CONSENT_VERSION = "2026-11-03"
CONSENT_EXPRESS = (
    "I want my Forgeway Pro access to start straight away, including during the free trial."
)
CONSENT_ACKNOWLEDGEMENT = (
    "I understand that once my access starts I lose my 14-day right to cancel and get a refund. "
    "I can still cancel at any time to stop future payments."
)


def plan_for(status: str | None, *, paused: bool = False) -> Plan:
    """The plan a subscription in `status` grants. No subscription, or a paused one, is Free."""
    return Plan.PRO if status in PRO_STATUSES and not paused else Plan.FREE


def first_charge_date(start: date, trial_days: int) -> date:
    """The day the first payment is taken: the trial's last day plus one, or today with none."""
    return start + timedelta(days=max(trial_days, 0))


def withdrawal_deadline(started_at: datetime, country: str | None) -> datetime | None:
    """When an EU customer's right to withdraw ends, or None outside the EU."""
    if country is None or country.upper() not in EU_COUNTRIES:
        return None
    return started_at + WITHDRAWAL_PERIOD


def renewal_cooling_off_deadline(
    *,
    started_at: datetime,
    trial_end: datetime | None,
    interval: Interval | None,
    current_period_end: datetime | None,
    now: datetime,
) -> datetime | None:
    """When the current renewal cooling-off period ends, or None outside one.

    It opens when a trial converts (at `trial_end`) and when an annual period renews (a year
    before `current_period_end`), but not for the first paid period of a contract that had no
    trial: the regulation-37 waiver covers that one."""
    if now < RENEWAL_COOLING_OFF_FROM:
        return None
    starts = [trial_end] if trial_end is not None else []
    if interval == "annual" and current_period_end is not None:
        period_start = _year_before(current_period_end)
        if period_start - started_at > timedelta(days=1):
            starts.append(period_start)
    open_until = [s + RENEWAL_COOLING_OFF for s in starts if s <= now < s + RENEWAL_COOLING_OFF]
    return max(open_until, default=None)


def _year_before(moment: datetime) -> datetime:
    try:
        return moment.replace(year=moment.year - 1)
    except ValueError:  # 29 February
        return moment.replace(year=moment.year - 1, day=28)


@dataclass(frozen=True)
class SubscriptionSnapshot:
    """A subscription as the processor reports it now (always re-fetched, never from an event)."""

    id: str
    customer_id: str
    status: str
    price_id: str | None
    interval: Interval | None
    started_at: datetime
    trial_end: datetime | None
    current_period_end: datetime | None
    cancel_at_period_end: bool
    cancel_at: datetime | None
    paused: bool
    resumes_at: datetime | None
    latest_invoice_id: str | None
    # The account id we put in the subscription's metadata at checkout, if any.
    user_id: str | None


@dataclass(frozen=True)
class CheckoutSnapshot:
    id: str
    customer_id: str | None
    subscription_id: str | None
    client_reference_id: str | None
    country: str | None  # the billing address's country, for the EU withdrawal control


@dataclass(frozen=True)
class InvoiceSnapshot:
    id: str
    subscription_id: str | None
    status: str | None
    amount_paid: int
    hosted_invoice_url: str | None


@dataclass(frozen=True)
class PriceSnapshot:
    id: str
    unit_amount: int | None
    currency: str
    tax_behavior: str | None
    interval: str | None  # "month" or "year"
    active: bool


@dataclass(frozen=True)
class BillingEvent:
    """A verified webhook event, reduced to the ids needed to re-fetch what it is about."""

    id: str
    type: str
    object_id: str | None
    customer_id: str | None
    subscription_id: str | None


@dataclass(frozen=True)
class CheckoutRequest:
    user_id: str
    customer_id: str
    price_id: str
    trial_days: int  # 0: no trial, and promotion codes are allowed instead
    success_url: str
    cancel_url: str
    # Shown next to Checkout's pay button, so the obligation to pay is unambiguous.
    submit_message: str


class InvalidSignatureError(Exception):
    """The webhook payload's signature did not verify."""


class BillingGateway(Protocol):
    """The payment processor. Implemented over the Stripe SDK in the infrastructure layer."""

    def verify_event(self, payload: bytes, signature: str) -> BillingEvent: ...
    def create_customer(self, user_id: str, email: str, name: str) -> str: ...
    def create_checkout(self, request: CheckoutRequest) -> tuple[str, str]:
        """Open a Checkout Session; returns its id and URL."""
        ...

    def create_portal(self, customer_id: str, return_url: str) -> str: ...
    def checkout_session(self, session_id: str) -> CheckoutSnapshot: ...
    def subscription(self, subscription_id: str) -> SubscriptionSnapshot: ...
    def invoice(self, invoice_id: str) -> InvoiceSnapshot: ...
    def paid_invoices(self, subscription_id: str, since: datetime) -> list[InvoiceSnapshot]:
        """The subscription's paid invoices created at or after `since`."""
        ...

    def price(self, price_id: str) -> PriceSnapshot: ...
    def pause(self, subscription_id: str, resumes_at: datetime) -> SubscriptionSnapshot: ...
    def resume(self, subscription_id: str) -> SubscriptionSnapshot: ...
    def cancel_now(self, subscription_id: str) -> SubscriptionSnapshot: ...
    def refund_invoice(self, invoice_id: str, amount: int) -> None: ...
