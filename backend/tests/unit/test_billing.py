"""Billing without a database: the status→plan mapping, dates, the Checkout parameters, webhook
signatures and the emails. The Stripe SDK is mocked; nothing touches the network."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from datetime import UTC, date, datetime
from unittest.mock import MagicMock

import pytest

from lattice.application import billing_emails as emails
from lattice.application.billing import Billing, submit_message
from lattice.application.errors import BillingUnavailableError
from lattice.domain.billing import (
    CheckoutRequest,
    InvalidSignatureError,
    first_charge_date,
    plan_for,
    withdrawal_deadline,
)
from lattice.domain.entitlements import Plan
from lattice.infrastructure.stripe_billing import StripeGateway, checkout_params
from lattice.settings import Settings

SECRET = "whsec_test_secret"


def signed(payload: str, secret: str = SECRET, at: int | None = None) -> str:
    """A `Stripe-Signature` header, made the way Stripe makes it."""
    at = at or int(time.time())
    digest = hmac.new(secret.encode(), f"{at}.{payload}".encode(), hashlib.sha256).hexdigest()
    return f"t={at},v1={digest}"


@pytest.mark.parametrize(
    ("status", "plan"),
    [
        ("trialing", Plan.PRO),
        ("active", Plan.PRO),
        ("past_due", Plan.PRO),
        ("canceled", Plan.FREE),
        ("unpaid", Plan.FREE),
        ("paused", Plan.FREE),
        ("incomplete", Plan.FREE),
        ("incomplete_expired", Plan.FREE),
        (None, Plan.FREE),
        ("something-new", Plan.FREE),
    ],
)
def test_every_status_maps_to_a_plan(status, plan):
    assert plan_for(status) is plan


@pytest.mark.parametrize("status", ["trialing", "active", "past_due"])
def test_a_paused_collection_returns_the_learner_to_free(status):
    assert plan_for(status, paused=True) is Plan.FREE


def test_the_first_charge_falls_the_day_the_trial_ends():
    assert first_charge_date(date(2026, 11, 3), 7) == date(2026, 11, 10)
    assert first_charge_date(date(2026, 12, 28), 7) == date(2027, 1, 4)
    assert first_charge_date(date(2026, 11, 3), 0) == date(2026, 11, 3)


def test_withdrawal_is_for_eu_customers_for_14_days():
    start = datetime(2026, 11, 3, 12, tzinfo=UTC)
    assert withdrawal_deadline(start, "IE") == datetime(2026, 11, 17, 12, tzinfo=UTC)
    assert withdrawal_deadline(start, "de") is not None
    assert withdrawal_deadline(start, "GB") is None
    assert withdrawal_deadline(start, None) is None


def request(trial_days: int = 7) -> CheckoutRequest:
    return CheckoutRequest(
        user_id="0b0f1e9e-0000-4000-8000-000000000001",
        customer_id="cus_123",
        price_id="price_annual",
        trial_days=trial_days,
        success_url="https://forgeway.dev/pro/success?session_id={CHECKOUT_SESSION_ID}",
        cancel_url="https://forgeway.dev/pro/cancelled",
        submit_message="Nothing is charged today.",
    )


def test_checkout_is_a_tax_inclusive_subscription_with_a_trial_and_no_coupon():
    params = checkout_params(request(trial_days=7))
    assert params["mode"] == "subscription"
    assert params["client_reference_id"] == "0b0f1e9e-0000-4000-8000-000000000001"
    assert params["customer"] == "cus_123"
    assert params["line_items"] == [{"price": "price_annual", "quantity": 1}]
    assert params["subscription_data"]["trial_period_days"] == 7
    assert params["subscription_data"]["metadata"] == {
        "user_id": "0b0f1e9e-0000-4000-8000-000000000001"
    }
    assert params["automatic_tax"] == {"enabled": True}
    assert params["tax_id_collection"] == {"enabled": True}
    assert params["customer_update"]["address"] == "auto"
    assert params["payment_method_collection"] == "always"
    # Never a trial and a coupon in one session.
    assert params["allow_promotion_codes"] is False
    assert "discounts" not in params
    assert params["custom_text"]["submit"]["message"] == "Nothing is charged today."
    assert params["success_url"].endswith("{CHECKOUT_SESSION_ID}")
    assert params["cancel_url"] == "https://forgeway.dev/pro/cancelled"


def test_without_a_trial_promotion_codes_are_allowed():
    params = checkout_params(request(trial_days=0))
    assert "trial_period_days" not in params["subscription_data"]
    assert params["allow_promotion_codes"] is True


def test_the_gateway_sends_the_checkout_parameters_to_stripe():
    client = MagicMock()
    client.v1.checkout.sessions.create.return_value = {"id": "cs_1", "url": "https://co/cs_1"}
    gateway = StripeGateway(client, SECRET)
    assert gateway.create_checkout(request()) == ("cs_1", "https://co/cs_1")
    client.v1.checkout.sessions.create.assert_called_once_with(params=checkout_params(request()))


def test_the_pay_button_message_names_the_amount_and_the_first_charge_date():
    now = datetime(2026, 11, 3, 9, tzinfo=UTC)
    message = submit_message("annual", 19000, 7, now)
    assert "Nothing is charged today" in message
    assert "£190 on 10 November 2026" in message
    assert "every year" in message
    assert submit_message("monthly", 1900, 0, now).startswith("You will be charged £19 today")


def event_payload(kind: str, obj: dict) -> str:
    return json.dumps({"id": "evt_1", "type": kind, "data": {"object": obj}})


def test_a_correctly_signed_event_is_read():
    gateway = StripeGateway(MagicMock(), SECRET)
    payload = event_payload(
        "customer.subscription.updated",
        {"id": "sub_1", "object": "subscription", "customer": "cus_1"},
    )
    event = gateway.verify_event(payload.encode(), signed(payload))
    assert (event.id, event.type, event.subscription_id, event.customer_id) == (
        "evt_1",
        "customer.subscription.updated",
        "sub_1",
        "cus_1",
    )


@pytest.mark.parametrize(
    "header",
    [
        lambda p: signed(p, secret="whsec_someone_else"),
        lambda p: signed(p, at=int(time.time()) - 3600),  # replayed an hour later
        lambda p: "t=1,v1=nonsense",
        lambda p: "",
    ],
)
def test_a_bad_signature_is_refused(header):
    gateway = StripeGateway(MagicMock(), SECRET)
    payload = event_payload("invoice.paid", {"id": "in_1", "object": "invoice"})
    with pytest.raises(InvalidSignatureError):
        gateway.verify_event(payload.encode(), header(payload))


def test_a_tampered_body_is_refused():
    gateway = StripeGateway(MagicMock(), SECRET)
    payload = event_payload("invoice.paid", {"id": "in_1", "object": "invoice"})
    header = signed(payload)
    with pytest.raises(InvalidSignatureError):
        gateway.verify_event(payload.replace("in_1", "in_2").encode(), header)


def test_an_invoice_event_names_its_subscription_in_the_clover_api():
    gateway = StripeGateway(MagicMock(), SECRET)
    payload = event_payload(
        "invoice.upcoming",
        {
            "object": "invoice",
            "customer": "cus_1",
            "parent": {"subscription_details": {"subscription": "sub_9"}},
        },
    )
    event = gateway.verify_event(payload.encode(), signed(payload))
    assert event.object_id is None and event.subscription_id == "sub_9"


def billing_with_prices(**overrides: object) -> Billing:
    gateway = MagicMock()
    prices = {
        "price_m": {"unit_amount": 1900, "interval": "month"},
        "price_a": {"unit_amount": 19000, "interval": "year"},
    }

    def price(price_id: str):
        spec = prices[price_id] | overrides
        snapshot = MagicMock()
        snapshot.unit_amount = spec["unit_amount"]
        snapshot.currency = spec.get("currency", "gbp")
        snapshot.tax_behavior = spec.get("tax_behavior", "inclusive")
        snapshot.interval = spec["interval"]
        snapshot.active = True
        return snapshot

    gateway.price.side_effect = price
    return Billing(
        gateway=gateway,
        price_ids={"monthly": "price_m", "annual": "price_a"},
        amounts={"monthly": 1900, "annual": 19000},
        trial_days=7,
        base_url="https://forgeway.dev",
    )


def test_matching_tax_inclusive_prices_pass_the_check_once():
    paid = billing_with_prices()
    assert paid.price_problems() == []
    paid.ensure_prices()
    paid.ensure_prices()
    assert paid.gateway.price.call_count == 4  # type: ignore[attr-defined]  # 2 in problems, 2 once


@pytest.mark.parametrize(
    ("override", "fragment"),
    [
        ({"tax_behavior": "exclusive"}, "not tax-inclusive"),
        ({"currency": "usd"}, "not GBP"),
        ({"unit_amount": 2000}, "the site shows"),
    ],
)
def test_a_price_mismatch_is_logged_loudly_and_refuses_checkout(override, fragment, caplog):
    paid = billing_with_prices(**override)
    with pytest.raises(BillingUnavailableError):
        paid.ensure_prices()
    errors = [r for r in caplog.records if r.levelname == "ERROR"]
    assert errors and any(fragment in r.getMessage() for r in errors)
    assert all("BILLING PRICE MISMATCH" in r.getMessage() for r in errors)


def test_billing_is_on_only_with_both_keys_and_both_prices():
    base = {"stripe_secret_key": "sk_test_x", "stripe_webhook_secret": "whsec_x"}
    prices = {"stripe_price_monthly": "price_m", "stripe_price_annual": "price_a"}
    assert Settings(_env_file=None).billing_enabled is False  # type: ignore[call-arg]
    assert Settings(_env_file=None, **base).billing_enabled is False  # type: ignore[call-arg, arg-type]
    assert Settings(_env_file=None, **base, **prices).billing_enabled is True  # type: ignore[call-arg, arg-type]
    defaults = Settings(_env_file=None)  # type: ignore[call-arg]
    assert (defaults.billing_trial_days, defaults.billing_monthly_price_minor) == (7, 1900)
    assert defaults.billing_annual_price_minor == 19000


RECIPIENT = emails.Recipient("ada@example.com", "Ada", "Europe/London")
LINKS = emails.Links("https://forgeway.dev")


def test_the_confirmation_repeats_the_pre_contract_information_and_the_consent():
    message = emails.confirmation(
        RECIPIENT,
        LINKS,
        interval="annual",
        amount=19000,
        trial_days=7,
        trial_end=datetime(2026, 11, 10, 9, tzinfo=UTC),
        consent_at=datetime(2026, 11, 3, 9, 30, tzinfo=UTC),
        consent_wording="I want my Forgeway Pro access to start straight away.",
    )
    text = message.text
    assert "7-day free trial" in text and "£0" in text
    assert "£190 will be taken on 10 November 2026" in text
    assert "£190 a year, including VAT" in text and "renews automatically every year" in text
    assert "cancel at any time" in text
    assert "capstone project" in text
    assert "3 November 2026 at 09:30 UTC" in text
    assert "“I want my Forgeway Pro access to start straight away.”" in text
    assert "https://forgeway.dev/terms" in text and "model cancellation form" in text
    assert "<script" not in message.html


def test_billing_emails_say_what_happens_and_when():
    trial = emails.trial_ending(
        RECIPIENT, LINKS, interval="monthly", amount=1900,
        trial_end=datetime(2026, 11, 10, 23, 30, tzinfo=UTC),
    )  # fmt: skip
    assert "ends on 10 November 2026" in trial.subject and "£19" in trial.text
    failed = emails.payment_failed(
        RECIPIENT, LINKS, amount=1900, update_url="https://invoice.stripe.com/i/x"
    )
    assert "https://invoice.stripe.com/i/x" in failed.text and "£19" in failed.text
    cancelled = emails.cancellation_confirmed(
        RECIPIENT, LINKS, ends_at=datetime(2026, 12, 3, tzinfo=UTC)
    )
    assert "keep Pro until 3 December 2026" in cancelled.text and "not be charged" in cancelled.text
    renewal = emails.renewal_reminder(
        RECIPIENT, LINKS, amount=19000, renews_at=datetime(2027, 11, 10, tzinfo=UTC)
    )
    assert "renews on 10 November 2027" in renewal.subject and "£190" in renewal.text
    assert "Open your map" in emails.onboarding_nudge(RECIPIENT, LINKS, trial_end=None).text


def test_dates_follow_the_learners_time_zone():
    late = datetime(2026, 11, 10, 23, 30, tzinfo=UTC)
    assert emails.day(late, "Asia/Tokyo") == "11 November 2026"
    assert emails.day(late, "Not/AZone") == "10 November 2026"
    assert emails.price(19000) == "£190" and emails.price(950) == "£9.50"
