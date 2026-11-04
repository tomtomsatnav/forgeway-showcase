"""The billing emails, in Forgeway's plain voice: what happened, what it costs, what to do.

Each returns an `EmailMessage`; callers send it after the transaction, as account emails are.
Dates are shown in the learner's own time zone. Prices include VAT, as everywhere a learner sees
one. The confirmation email repeats the pre-contract information and the regulation-37 consent.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from html import escape
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from lattice.domain.billing import Interval
from lattice.domain.email import EmailMessage

PRO_INCLUDES = (
    "the capstone project that closes every track",
    "the guided projects, which build one codebase across several tracks",
    "every exercise past the free ones",
    "certificates you can make public and share",
)
PERIOD = {"monthly": "month", "annual": "year"}


@dataclass(frozen=True)
class Recipient:
    email: str
    name: str
    time_zone: str  # IANA


@dataclass(frozen=True)
class Links:
    base_url: str

    def at(self, path: str) -> str:
        return f"{self.base_url.rstrip('/')}{path}"

    @property
    def billing(self) -> str:
        return self.at("/profile#billing")


def price(minor: int) -> str:
    """ "£19", "£9.50"."""
    pounds, pence = divmod(minor, 100)
    return f"£{pounds:,}" if pence == 0 else f"£{pounds:,}.{pence:02d}"


def day(when: datetime | date, time_zone: str = "UTC") -> str:
    """ "10 November 2026", on the learner's calendar."""
    if isinstance(when, datetime):
        try:
            zone = ZoneInfo(time_zone)
        except (ZoneInfoNotFoundError, ValueError):
            zone = ZoneInfo("UTC")
        when = when.astimezone(zone).date()
    return f"{when.day} {when:%B %Y}"


def _email(
    to: Recipient, subject: str, paragraphs: list[str], link: str, action: str
) -> EmailMessage:
    html = "".join(f"<p>{escape(p)}</p>".replace("\n", "<br>") for p in paragraphs)
    return EmailMessage(
        to=to.email,
        subject=subject,
        text="\n\n".join([f"Hello {to.name},", *paragraphs, f"{action}: {link}"]),
        html=(
            f"<p>Hello {escape(to.name)},</p>{html}"
            f'<p><a href="{escape(link)}">{escape(action)}</a></p>'
        ),
    )


def _renewal_terms(interval: Interval, amount: int) -> str:
    return (
        f"Forgeway Pro costs {price(amount)} a {PERIOD[interval]}, including VAT. It renews "
        f"automatically every {PERIOD[interval]} until you cancel. You can cancel at any time from "
        "your profile (Manage billing); you keep Pro until the end of the period you have paid for."
    )


def confirmation(
    to: Recipient,
    links: Links,
    *,
    interval: Interval,
    amount: int,
    trial_days: int,
    trial_end: datetime | None,
    consent_at: datetime | None,
    consent_wording: str | None,
) -> EmailMessage:
    """After Checkout: the contract confirmed on a durable medium (CCRs 2013, regulation 16)."""
    first_charge = (
        f"Your {trial_days}-day free trial has started and nothing has been "
        f"charged today (£0). Your first payment of {price(amount)} will be taken on "
        f"{day(trial_end, to.time_zone)} unless you cancel before then."
        if trial_end is not None
        else f"Your first payment of {price(amount)} has been taken."
    )
    consent = (
        f"Before you subscribed, on {day(consent_at, to.time_zone)} at "
        f"{consent_at.astimezone(UTC):%H:%M} UTC, you agreed to this:\n“{consent_wording}”"
        if consent_at is not None and consent_wording is not None
        else ""
    )
    return _email(
        to,
        "Welcome to Forgeway Pro",
        [
            p
            for p in [
                "Thank you for subscribing to Forgeway Pro. This email confirms your subscription; "
                "keep it for your records.",
                "Pro includes " + ", ".join(PRO_INCLUDES[:-1]) + f" and {PRO_INCLUDES[-1]}.",
                first_charge,
                _renewal_terms(interval, amount),
                consent,
                "The terms, the cancellation policy and the model cancellation form are at "
                f"{links.at('/terms')}; the privacy policy is at {links.at('/privacy')}.",
            ]
            if p
        ],
        links.billing,
        "Manage your subscription",
    )


def trial_ending(
    to: Recipient, links: Links, *, interval: Interval, amount: int, trial_end: datetime
) -> EmailMessage:
    """Three days before the trial ends (`customer.subscription.trial_will_end`)."""
    return _email(
        to,
        f"Your Forgeway Pro trial ends on {day(trial_end, to.time_zone)}",
        [
            f"Your free trial of Forgeway Pro ends on {day(trial_end, to.time_zone)}. Unless you "
            f"cancel before then, your card will be charged {price(amount)} that day, and every "
            f"{PERIOD[interval]} after that until you cancel.",
            "To keep Pro, you need do nothing. To stop, cancel from your profile (Manage billing) "
            "before the trial ends and you will not be charged.",
        ],
        links.billing,
        "Manage your subscription",
    )


def payment_failed(
    to: Recipient, links: Links, *, amount: int | None, update_url: str | None
) -> EmailMessage:
    """A renewal payment failed (`invoice.payment_failed`). Stripe retries it for a while."""
    owed = f" of {price(amount)}" if amount else ""
    return _email(
        to,
        "Your Forgeway Pro payment did not go through",
        [
            f"We could not take your payment{owed} for Forgeway Pro. You keep Pro for now while we "
            "try again over the next few days.",
            "To sort it out, pay the invoice with another card at the link below. You can also "
            "update your card from your profile (Manage billing).",
        ],
        update_url or links.billing,
        "Update your payment details",
    )


def cancellation_confirmed(
    to: Recipient, links: Links, *, ends_at: datetime | None
) -> EmailMessage:
    """Within 24 hours of an online cancellation: the end-of-contract confirmation."""
    until = (
        f"You keep Pro until {day(ends_at, to.time_zone)}, and then your account returns to "
        "the free plan."
        if ends_at is not None
        else "Your account is now on the free plan."
    )
    return _email(
        to,
        "Your Forgeway Pro subscription is cancelled",
        [
            f"This confirms that your Forgeway Pro subscription is cancelled. {until} You will not "
            "be charged again.",
            "Everything you have passed, and any certificate you made public, stays yours. If you "
            "change your mind before the end date, you can renew from your profile.",
        ],
        links.billing,
        "Your subscription",
    )


def withdrawal_confirmed(to: Recipient, links: Links, *, refunded: int) -> EmailMessage:
    """After the EU "Withdraw from contract" control: the contract ends at once."""
    refund = (
        f"We have refunded {price(refunded)} to your card; it can take up to 10 days to appear."
        if refunded > 0
        else "Nothing had been charged, so there is nothing to refund."
    )
    return _email(
        to,
        "You have withdrawn from your Forgeway Pro contract",
        [
            "This confirms that you have withdrawn from your Forgeway Pro contract. It has ended "
            "today and your account is back on the free plan. You will not be charged again.",
            refund,
        ],
        links.billing,
        "Your account",
    )


def withdrawal_processing(to: Recipient, links: Links, *, refunded: int) -> EmailMessage:
    """After a withdrawal whose refund went through but whose cancellation Stripe refused: the
    owner finishes it by hand."""
    refund = (
        f"We have refunded {price(refunded)} to your card; it can take up to 10 days to appear."
        if refunded > 0
        else "Nothing had been charged, so there is nothing to refund."
    )
    return _email(
        to,
        "Your withdrawal from Forgeway Pro is being processed",
        [
            "We have received your withdrawal from your Forgeway Pro contract. " + refund,
            "Ending the subscription itself is taking a little longer than usual. We are "
            "processing it and will email you when it is done. You will not be charged again.",
        ],
        links.billing,
        "Your account",
    )


def renewal_reminder(
    to: Recipient, links: Links, *, amount: int, renews_at: datetime
) -> EmailMessage:
    """Before an annual renewal (`invoice.upcoming`; its lead time is set in Stripe)."""
    return _email(
        to,
        f"Your Forgeway Pro subscription renews on {day(renews_at, to.time_zone)}",
        [
            f"Your annual Forgeway Pro subscription renews automatically on "
            f"{day(renews_at, to.time_zone)}, when your card will be charged {price(amount)} "
            "for another year, including VAT.",
            "To keep Pro, you need do nothing. To stop it renewing, cancel from your profile "
            "(Manage billing) before that date; you keep Pro until then.",
        ],
        links.billing,
        "Manage your subscription",
    )


def onboarding_nudge(to: Recipient, links: Links, *, trial_end: datetime | None) -> EmailMessage:
    """Day 3 of a trial with no exercise passed and no live run yet."""
    ends = f" Your trial runs until {day(trial_end, to.time_zone)}." if trial_end else ""
    return _email(
        to,
        "Pick up where you left off on Forgeway",
        [
            "You started your Forgeway Pro trial a few days ago. The quickest way to see what it "
            "is like is to pass one exercise: open the map, choose the next one on your track and "
            f"run the checks. Most take under half an hour.{ends}",
            "If Forgeway is not for you, you can cancel from your profile before the trial ends "
            "and you will not be charged.",
        ],
        links.at("/"),
        "Open your map",
    )
