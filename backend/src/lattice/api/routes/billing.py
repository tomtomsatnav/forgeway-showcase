"""Paid subscriptions (docs/plans/billing.md): Checkout, the Customer Portal, pause and resume,
EU withdrawal and the Stripe webhook.

Every route but the status answers 503 `billing-unavailable` while billing is off. The webhook
takes no session and no CSRF token: it is authenticated by Stripe's signature over the raw body,
and rate-limited per client IP before the signature is checked.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Header, Request, Response
from sqlalchemy.orm import Session

from lattice.api import errors, schemas
from lattice.api.deps import ClientIp, CurrentLearner, Db, MutatingLearner, State, VerifiedLearner
from lattice.api.schemas import PROBLEM_RESPONSES
from lattice.application import billing
from lattice.application.errors import BillingUnavailableError
from lattice.domain.billing import (
    CONSENT_ACKNOWLEDGEMENT,
    CONSENT_EXPRESS,
    CONSENT_VERSION,
    InvalidSignatureError,
)
from lattice.domain.email import EmailMessage, EmailSender
from lattice.infrastructure.db.engine import transaction
from lattice.infrastructure.db.models import User
from lattice.infrastructure.stripe_billing import StripeGateway
from lattice.settings import Settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/billing", tags=["billing"], responses=PROBLEM_RESPONSES)
MAX_WEBHOOK_BYTES = 256 * 1024  # Stripe events are a few kilobytes


def build_billing(settings: Settings) -> billing.Billing | None:
    """Billing from the environment, or None while any key or price id is missing, or while
    the trader's address is unset (the law requires it before taking money)."""
    if not settings.billing_enabled:
        return None
    if not (settings.trader_address or "").strip():
        logger.error(
            "BILLING OFF: LATTICE_TRADER_ADDRESS is unset. The trader's UK address must be shown "
            "before taking payments (see deploy/vps/README.md, Billing)."
        )
        return None
    assert settings.stripe_secret_key and settings.stripe_webhook_secret  # noqa: S101
    assert settings.stripe_price_monthly and settings.stripe_price_annual  # noqa: S101
    return billing.Billing(
        gateway=StripeGateway.from_keys(
            settings.stripe_secret_key.get_secret_value(),
            settings.stripe_webhook_secret.get_secret_value(),
        ),
        price_ids={
            "monthly": settings.stripe_price_monthly,
            "annual": settings.stripe_price_annual,
        },
        amounts={
            "monthly": settings.billing_monthly_price_minor,
            "annual": settings.billing_annual_price_minor,
        },
        trial_days=settings.billing_trial_days,
        base_url=settings.public_base_url,
    )


def billing_config(settings: Settings, enabled: bool) -> schemas.BillingConfig:
    """The `billing` block of `/api/config`."""
    days = settings.billing_trial_days
    return schemas.BillingConfig(
        enabled=enabled,
        currency="GBP",
        monthly_price_minor=settings.billing_monthly_price_minor,
        annual_price_minor=settings.billing_annual_price_minor,
        intro_offer=schemas.IntroOffer(kind="trial_days", value=days) if days > 0 else None,
    )


def _on(state: State) -> billing.Billing:
    if state.billing is None:
        raise BillingUnavailableError("Subscriptions are not available.")
    return state.billing


def _send(sender: EmailSender, messages: list[EmailMessage]) -> None:
    """After the response and the commit; a failing provider is logged, never retried here."""
    for message in messages:
        try:
            sender.send(message)
        except Exception:
            logger.exception("billing email could not be sent", extra={"subject": message.subject})


def _status(db: Session, state: State, user: User) -> schemas.BillingStatus:
    seen = billing.view(db, state.billing, user)
    sub = seen.subscription
    return schemas.BillingStatus(
        enabled=seen.enabled,
        plan=seen.plan.value,
        trial_days=seen.trial_days,
        subscription=None
        if sub is None
        else schemas.SubscriptionInfo(
            status=sub.status,
            interval=sub.interval,
            paused=sub.paused,
            resumes_at=sub.resumes_at,
            trial_end=sub.trial_end,
            current_period_end=sub.current_period_end,
            cancelling=sub.cancelling,
            ends_at=sub.ends_at,
            withdrawal_until=sub.withdrawal_until,
        ),
        consent=schemas.BillingConsentWording(
            version=CONSENT_VERSION,
            express=CONSENT_EXPRESS,
            acknowledgement=CONSENT_ACKNOWLEDGEMENT,
        ),
    )


@router.get("")
def status(learner: CurrentLearner, db: Db, state: State) -> schemas.BillingStatus:
    """The learner's plan and subscription, the trial they would get now, and the consent
    wording to show before Checkout."""
    return _status(db, state, learner.user)


@router.post("/checkout")
def checkout(
    body: schemas.CheckoutStart, learner: VerifiedLearner, db: Db, state: State
) -> schemas.BillingRedirect:
    """Record the regulation-37 consent (422 `consent-required` without it, in the current
    wording), then open a Stripe Checkout Session for the chosen plan. 409 if the learner
    already has a live subscription."""
    on = _on(state)
    state.limiter.check(
        f"billing-checkout:user:{learner.user.id}",
        limit=state.settings.billing_checkouts_per_hour,
        window=timedelta(hours=1),
        message="Too many tries. Try again later.",
    )
    url = billing.start_checkout(
        db,
        on,
        learner.user,
        body.plan,
        consent=body.consent,
        consent_version=body.consent_version,
        marketing_opt_out=body.marketing_opt_out,
    )
    return schemas.BillingRedirect(url=url)


def _limit(state: State, learner: CurrentLearner) -> None:
    """Portal, pause, resume and withdraw each call Stripe: a per-account hourly limit."""
    state.limiter.check(
        f"billing-manage:user:{learner.user.id}",
        limit=state.settings.billing_actions_per_hour,
        window=timedelta(hours=1),
        message="Too many tries. Try again later.",
    )


@router.post("/portal")
def portal(learner: MutatingLearner, db: Db, state: State) -> schemas.BillingRedirect:
    """A Stripe Customer Portal session: cancel, switch plan, invoices and payment methods."""
    on = _on(state)
    _limit(state, learner)
    return schemas.BillingRedirect(url=billing.portal_url(db, on, learner.user))


@router.post("/pause")
def pause(
    body: schemas.BillingPause, learner: MutatingLearner, db: Db, state: State
) -> schemas.BillingStatus:
    """Pause payments, and Pro with them, for one to three months."""
    on = _on(state)
    _limit(state, learner)
    billing.pause(db, on, learner.user, body.months)
    return _status(db, state, learner.user)


@router.post("/resume")
def resume(learner: MutatingLearner, db: Db, state: State) -> schemas.BillingStatus:
    """Resume a paused subscription now."""
    on = _on(state)
    _limit(state, learner)
    billing.resume(db, on, learner.user)
    return _status(db, state, learner.user)


@router.post("/withdraw")
def withdraw(
    learner: MutatingLearner, state: State, background: BackgroundTasks
) -> schemas.BillingStatus:
    """Withdraw from the contract while `withdrawal_until` is set (EU customers within 14 days
    of the contract; from 2027, anyone within 14 days of a trial converting or an annual
    renewal): every payment in the period is refunded, then it ends now. 409 outside those
    periods; 503 `billing-unavailable`, with nothing cancelled, if the refund fails."""
    on = _on(state)
    _limit(state, learner)
    # Its own transaction, committed before the email goes and with no row lock held while it
    # is sent, as in the webhook.
    with transaction(state.sessions) as session:
        user = session.get(User, learner.user.id)
        assert user is not None  # noqa: S101 - the learner was just resolved
        message = billing.withdraw(session, on, user)
        result = _status(session, state, user)
    background.add_task(_send, state.email, [message])
    return result


async def _raw_body(request: Request) -> bytes:
    return await request.body()


@router.post("/webhook", include_in_schema=False)
def webhook(
    body: Annotated[bytes, Depends(_raw_body)],
    state: State,
    ip: ClientIp,
    background: BackgroundTasks,
    stripe_signature: Annotated[str | None, Header()] = None,
) -> Response:
    """Stripe's events. Verified on the raw body, processed once per event id."""
    on = _on(state)
    state.limiter.check(
        f"billing-webhook:ip:{ip}",
        limit=state.settings.billing_webhooks_per_minute,
        window=timedelta(minutes=1),
        message="Too many requests.",
    )
    if len(body) > MAX_WEBHOOK_BYTES or not stripe_signature:
        return errors.problem(400, "Bad request", "Missing signature.", "invalid-signature")
    try:
        event = on.gateway.verify_event(body, stripe_signature)
    except InvalidSignatureError:
        logger.warning("billing webhook with a bad signature", extra={"ip": ip})
        return errors.problem(400, "Bad request", "Invalid signature.", "invalid-signature")
    with transaction(state.sessions) as session:
        messages = billing.handle_event(session, on, event)
    background.add_task(_send, state.email, messages)
    return Response(status_code=200, content='{"received":true}', media_type="application/json")
