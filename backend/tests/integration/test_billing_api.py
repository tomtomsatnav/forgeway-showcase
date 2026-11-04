"""Billing through the API against a real database, with the Stripe SDK mocked.

`FakeStripe` stands in for `stripe.StripeClient`: it keeps subscriptions, sessions and invoices in
dicts and answers the calls `StripeGateway` makes. Webhooks are signed with the test secret and
verified by the real SDK code, so signature checks are the real ones. Nothing touches the network.
"""

from __future__ import annotations

import hashlib
import hmac
import itertools
import json
import logging
import time
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError
from typer.testing import CliRunner

from lattice.api.app import create_app
from lattice.application import billing as billing_app
from lattice.application.billing import Billing
from lattice.application.content_sync import sync_content
from lattice.cli import app as cli_app
from lattice.domain.billing import CONSENT_VERSION
from lattice.domain.email import EmailMessage
from lattice.infrastructure.db.engine import transaction
from lattice.infrastructure.db.models import (
    AccountToken,
    BillingConsent,
    BillingEvent,
    ExerciseProgress,
    ProWaitlistEntry,
    Subscription,
    User,
)
from lattice.infrastructure.stripe_billing import StripeGateway
from lattice.settings import Settings
from tests.integration.test_api import ORIGIN, sign_up

SECRET = "whsec_test"
NOW = datetime.now(UTC).replace(microsecond=0)
DAY = timedelta(days=1)


def ts(when: datetime) -> int:
    return int(when.timestamp())


class Outbox:
    """An `EmailSender` that keeps everything it is given."""

    def __init__(self) -> None:
        self.sent: list[EmailMessage] = []

    def send(self, message: EmailMessage) -> None:
        self.sent.append(message)

    def latest(self, to: str) -> EmailMessage | None:
        return next((m for m in reversed(self.sent) if m.to == to), None)

    def subjects(self, to: str = "ada@example.com") -> list[str]:
        return [
            m.subject for m in self.sent if m.to == to and "Confirm your email" not in m.subject
        ]


class FakeStripe:
    """The parts of `stripe.StripeClient` that billing calls, over in-memory objects."""

    def __init__(self) -> None:
        self.subs: dict[str, dict[str, Any]] = {}
        self.sessions: dict[str, dict[str, Any]] = {}
        self.invoices: dict[str, dict[str, Any]] = {}
        self.prices = {
            "price_m": {"id": "price_m", "unit_amount": 1900, "currency": "gbp",
                        "tax_behavior": "inclusive", "recurring": {"interval": "month"},
                        "active": True},
            "price_a": {"id": "price_a", "unit_amount": 19000, "currency": "gbp",
                        "tax_behavior": "inclusive", "recurring": {"interval": "year"},
                        "active": True},
        }  # fmt: skip
        self.ids = itertools.count(1)
        self.client = MagicMock()
        v1 = self.client.v1
        v1.customers.create.side_effect = lambda params, options: {"id": f"cus_{next(self.ids)}"}
        v1.checkout.sessions.create.side_effect = self._create_session
        v1.checkout.sessions.retrieve.side_effect = lambda sid: self.sessions[sid]
        v1.subscriptions.retrieve.side_effect = lambda sid: self.subs[sid]
        v1.subscriptions.update.side_effect = self._update
        v1.subscriptions.cancel.side_effect = self._cancel
        v1.invoices.retrieve.side_effect = lambda iid: self.invoices[iid]
        v1.invoices.list.side_effect = self._list_invoices
        v1.prices.retrieve.side_effect = lambda pid: self.prices[pid]
        v1.billing_portal.sessions.create.side_effect = lambda params: {
            "url": f"https://billing.stripe.com/p/{params['customer']}"
        }

    def _list_invoices(self, params: dict[str, Any]) -> dict[str, Any]:
        return {
            "data": [
                invoice
                for invoice in self.invoices.values()
                if invoice.get("subscription") == params["subscription"]
                and invoice["status"] == params["status"]
                and invoice["created"] >= params["created"]["gte"]
            ]
        }

    def paid(self, iid: str, amount: int, created: datetime = NOW, sid: str = "sub_1") -> None:
        self.invoices[iid] = {
            "id": iid, "status": "paid", "amount_paid": amount, "subscription": sid,
            "created": ts(created),
        }  # fmt: skip

    def _create_session(self, params: dict[str, Any]) -> dict[str, Any]:
        sid = f"cs_{next(self.ids)}"
        self.sessions[sid] = {"id": sid, "customer": params["customer"], "subscription": None,
                              "client_reference_id": params["client_reference_id"],
                              "params": params}  # fmt: skip
        return {"id": sid, "url": f"https://checkout.stripe.com/c/{sid}"}

    def _update(self, sid: str, params: dict[str, Any]) -> dict[str, Any]:
        pause = params.get("pause_collection")
        self.subs[sid]["pause_collection"] = pause or None
        return self.subs[sid]

    def _cancel(self, sid: str) -> dict[str, Any]:
        self.subs[sid]["status"] = "canceled"
        return self.subs[sid]

    def subscribe(
        self,
        customer: str,
        status: str = "trialing",
        *,
        sid: str = "sub_1",
        price: str = "price_a",
        user_id: str | None = None,
        started: datetime = NOW,
        trial_days: int = 7,
        **fields: Any,
    ) -> dict[str, Any]:
        interval = self.prices[price]["recurring"]["interval"]
        period_end = started + (DAY * 365 if interval == "year" else DAY * 30)
        self.subs[sid] = {
            "id": sid, "object": "subscription", "customer": customer, "status": status,
            "start_date": ts(started),
            "trial_end": ts(started + DAY * trial_days) if trial_days else None,
            "cancel_at_period_end": False, "cancel_at": None, "pause_collection": None,
            "latest_invoice": None, "metadata": {"user_id": user_id} if user_id else {},
            "items": {"data": [{"price": self.prices[price],
                                "current_period_end": ts(period_end)}]},
        } | fields  # fmt: skip
        return self.subs[sid]


@pytest.fixture
def stripe_fake() -> FakeStripe:
    return FakeStripe()


@pytest.fixture
def outbox() -> Outbox:
    return Outbox()


def settings_for(engine, tmp_path, **overrides: Any) -> Settings:
    return Settings(
        _env_file=None,  # type: ignore[call-arg]
        content_dir=tmp_path,
        database_url=str(engine.url),
        allowed_origins="",
        log_level="WARNING",
        public_base_url="https://forgeway.test",
        **overrides,
    )


def make_billing(fake: FakeStripe, trial_days: int = 7) -> Billing:
    return Billing(
        gateway=StripeGateway(fake.client, SECRET),
        price_ids={"monthly": "price_m", "annual": "price_a"},
        amounts={"monthly": 1900, "annual": 19000},
        trial_days=trial_days,
        base_url="https://forgeway.test",
    )


@pytest.fixture
def make_client(engine, factory, catalogue, tmp_path, outbox) -> Iterator[Any]:
    with transaction(factory) as session:
        sync_content(session, catalogue.graph)
    clients: list[TestClient] = []

    def make(billing: Billing | None = None, **overrides: Any) -> TestClient:
        app = create_app(
            settings_for(engine, tmp_path, **overrides),
            engine=engine,
            email=outbox,
            billing_override=billing,
        )
        client = TestClient(app, headers={"origin": ORIGIN})
        client.__enter__()
        clients.append(client)
        return client

    yield make
    for client in clients:
        client.__exit__(None, None, None)


@pytest.fixture
def client(make_client, stripe_fake) -> TestClient:
    return make_client(make_billing(stripe_fake))


def csrf(me: dict) -> dict[str, str]:
    return {"x-csrf-token": me["csrf_token"]}


def start(client: TestClient, me: dict, plan: str = "annual", **body: Any):
    return client.post(
        "/api/billing/checkout",
        json={"plan": plan, "consent": True, "consent_version": CONSENT_VERSION} | body,
        headers=csrf(me),
    )


def deliver(client: TestClient, kind: str, obj: dict[str, Any], event_id: str | None = None):
    payload = json.dumps(
        {"id": event_id or f"evt_{kind}_{obj.get('id')}", "type": kind, "data": {"object": obj}}
    )
    at = int(time.time())
    digest = hmac.new(SECRET.encode(), f"{at}.{payload}".encode(), hashlib.sha256).hexdigest()
    return client.post(
        "/api/billing/webhook",
        content=payload,
        headers={"stripe-signature": f"t={at},v1={digest}", "content-type": "application/json"},
    )


def subscribed(client: TestClient, fake: FakeStripe, me: dict, status: str = "trialing", **kw):
    """Checkout, then Stripe's completion webhook, as a learner finishing Checkout sees it."""
    opened = start(client, me)
    assert opened.status_code == 200, opened.text
    sid = opened.json()["url"].rsplit("/", 1)[1]
    session = fake.sessions[sid]
    fake.subscribe(session["customer"], status, user_id=me["id"], **kw)
    session.update(subscription="sub_1", customer_details={"address": {"country": "GB"}})
    completed = {"id": sid, "object": "checkout.session"}
    assert deliver(client, "checkout.session.completed", completed).status_code == 200
    return session


def plan_of(factory, email: str = "ada@example.com") -> str:
    with factory() as session:
        return session.scalars(select(User.plan).where(User.email == email)).one()


# --- Billing off -----------------------------------------------------------------------------


def test_with_billing_off_the_config_shows_the_prices_but_nothing_is_on_sale(make_client, factory):
    client = make_client()
    assert client.get("/api/config").json()["billing"] == {
        "enabled": False,
        "currency": "GBP",
        "monthly_price_minor": 1900,
        "annual_price_minor": 19000,
        "intro_offer": {"kind": "trial_days", "value": 7},
    }
    me = sign_up(client)
    status = client.get("/api/billing").json()
    assert status["enabled"] is False and status["subscription"] is None
    refused = start(client, me)
    assert refused.status_code == 503 and refused.json()["code"] == "billing-unavailable"
    assert client.post("/api/billing/webhook", content=b"{}").status_code == 503
    # The waitlist works exactly as before.
    joined = client.post("/api/pro/waitlist", json={"plan": "pro"}, headers=csrf(me))
    assert joined.status_code == 200 and joined.json()["joined"] is True
    assert plan_of(factory) == "free"


def test_the_config_shape_with_billing_on(make_client, stripe_fake):
    on = make_client(make_billing(stripe_fake), billing_trial_days=7)
    assert on.get("/api/config").json()["billing"] == {
        "enabled": True,
        "currency": "GBP",
        "monthly_price_minor": 1900,
        "annual_price_minor": 19000,
        "intro_offer": {"kind": "trial_days", "value": 7},
    }
    no_trial = make_client(make_billing(stripe_fake, 0), billing_trial_days=0)
    assert no_trial.get("/api/config").json()["billing"]["intro_offer"] is None


def test_the_config_serves_the_trader_address_once_it_is_set(make_client):
    assert make_client().get("/api/config").json()["trader_address"] is None
    assert make_client(trader_address="  ").get("/api/config").json()["trader_address"] is None
    served = make_client(trader_address=" 1 Example St, London ").get("/api/config").json()
    assert served["trader_address"] == "1 Example St, London"
    assert served["billing"]["enabled"] is False  # setting it does not switch billing on


# --- Checkout --------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "body",
    [{"consent": False}, {"consent_version": "2020-01-01"}],
    ids=["not ticked", "old wording"],
)
def test_checkout_needs_the_recorded_consent_first(client, stripe_fake, factory, body):
    me = sign_up(client)
    refused = start(client, me, **body)
    assert refused.status_code == 422 and refused.json()["code"] == "consent-required"
    stripe_fake.client.v1.checkout.sessions.create.assert_not_called()
    stripe_fake.client.v1.customers.create.assert_not_called()
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(BillingConsent)) == 0


def test_checkout_needs_a_verified_email(client):
    me = sign_up(client, verified=False)
    assert start(client, me).json()["code"] == "email-unverified"


def test_checkout_records_the_consent_and_opens_a_trial_session(client, stripe_fake, factory):
    me = sign_up(client)
    opened = start(client, me, plan="annual")
    assert opened.status_code == 200, opened.text
    url = opened.json()["url"]
    assert url.startswith("https://checkout.stripe.com/c/cs_")
    params = stripe_fake.client.v1.checkout.sessions.create.call_args.kwargs["params"]
    assert params["client_reference_id"] == me["id"]
    assert params["line_items"] == [{"price": "price_a", "quantity": 1}]
    assert params["subscription_data"]["trial_period_days"] == 7
    assert params["automatic_tax"] == {"enabled": True}
    assert params["allow_promotion_codes"] is False  # a trial, so no coupon
    assert params["success_url"] == (
        "https://forgeway.test/pro/success?session_id={CHECKOUT_SESSION_ID}"
    )
    assert "£190 on" in params["custom_text"]["submit"]["message"]
    with factory() as session:
        consent = session.scalars(select(BillingConsent)).one()
        assert consent.wording_version == CONSENT_VERSION
        assert consent.plan == "annual"
        assert consent.checkout_session_id == url.rsplit("/", 1)[1]
        assert "14-day right to cancel" in consent.wording
    # Opening Checkout again reuses the customer.
    assert start(client, me, plan="monthly").status_code == 200
    assert stripe_fake.client.v1.customers.create.call_count == 1


def test_a_price_mismatch_refuses_checkout(client, stripe_fake, caplog):
    stripe_fake.prices["price_a"]["tax_behavior"] = "exclusive"
    me = sign_up(client)
    refused = start(client, me)
    assert refused.status_code == 503 and refused.json()["code"] == "billing-unavailable"
    assert any("BILLING PRICE MISMATCH" in r.getMessage() for r in caplog.records)
    stripe_fake.client.v1.checkout.sessions.create.assert_not_called()


def test_two_first_checkouts_racing_share_one_row(client, stripe_fake, factory):
    me = sign_up(client)

    def other_tab_wins(params: dict[str, Any], options: dict[str, Any]) -> dict[str, str]:
        with transaction(factory) as other:
            other.add(
                Subscription(
                    user_id=uuid.UUID(me["id"]), stripe_customer_id="cus_race", trial_used=False
                )
            )
        return {"id": "cus_race"}

    stripe_fake.client.v1.customers.create.side_effect = other_tab_wins
    opened = start(client, me)
    assert opened.status_code == 200, opened.text
    params = stripe_fake.client.v1.checkout.sessions.create.call_args.kwargs["params"]
    assert params["customer"] == "cus_race"
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(Subscription)) == 1


# --- Webhooks --------------------------------------------------------------------------------


def test_a_badly_signed_webhook_is_refused_and_not_recorded(client, factory):
    payload = json.dumps({"id": "evt_x", "type": "invoice.paid", "data": {"object": {}}})
    bad = client.post(
        "/api/billing/webhook", content=payload, headers={"stripe-signature": "t=1,v1=00"}
    )
    assert bad.status_code == 400 and bad.json()["code"] == "invalid-signature"
    unsigned = client.post("/api/billing/webhook", content=payload)
    assert unsigned.status_code == 400
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(BillingEvent)) == 0


def test_the_webhook_needs_no_session_or_csrf_token(client, stripe_fake):
    # Signed, unknown kind: accepted and ignored.
    assert deliver(client, "customer.created", {"id": "cus_9", "object": "customer"}).json() == {
        "received": True
    }


def test_completing_checkout_grants_pro_and_sends_the_confirmation(
    client, stripe_fake, factory, outbox
):
    me = sign_up(client)
    client.post("/api/pro/waitlist", json={"plan": "pro"}, headers=csrf(me))
    subscribed(client, stripe_fake, me)
    assert plan_of(factory) == "pro"
    assert client.get("/api/auth/me").json()["plan"] == "pro"
    status = client.get("/api/billing").json()
    assert status["subscription"]["status"] == "trialing"
    assert status["subscription"]["interval"] == "annual"
    assert status["subscription"]["trial_end"] is not None
    assert status["trial_days"] == 0  # no second trial
    confirmation = outbox.latest("ada@example.com")
    assert confirmation is not None and confirmation.subject == "Welcome to Forgeway Pro"
    assert "14-day right to cancel" in confirmation.text and "£0" in confirmation.text
    with factory() as session:
        # A free learner on the waitlist keeps their waitlist record.
        assert session.get(ProWaitlistEntry, session.scalars(select(User.id)).one()) is not None


def test_the_same_event_twice_is_processed_once(client, stripe_fake, factory, outbox):
    me = sign_up(client)
    session = subscribed(client, stripe_fake, me)
    calls = stripe_fake.client.v1.subscriptions.retrieve.call_count
    sent = len(outbox.sent)
    again = deliver(
        client, "checkout.session.completed", {"id": session["id"], "object": "checkout.session"}
    )
    assert again.status_code == 200
    assert stripe_fake.client.v1.subscriptions.retrieve.call_count == calls
    assert len(outbox.sent) == sent
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(BillingEvent)) == 1


def test_out_of_order_events_converge_on_stripes_current_state(client, stripe_fake, factory):
    me = sign_up(client)
    subscribed(client, stripe_fake, me, status="active", trial_days=0)
    stripe_fake.subs["sub_1"]["status"] = "canceled"
    assert (
        deliver(
            client,
            "customer.subscription.deleted",
            {"id": "sub_1", "object": "subscription"},
            "evt_2",
        ).status_code
        == 200
    )
    assert plan_of(factory) == "free"
    # A late `updated` from before the cancellation: its copy says active, Stripe says canceled.
    late = {"id": "sub_1", "object": "subscription", "status": "active"}
    assert deliver(client, "customer.subscription.updated", late, "evt_1").status_code == 200
    assert plan_of(factory) == "free"


def test_a_first_event_fetches_again_under_the_customers_lock(client, stripe_fake, factory):
    me = sign_up(client)
    opened = start(client, me)
    customer = stripe_fake.sessions[opened.json()["url"].rsplit("/", 1)[1]]["customer"]
    stripe_fake.subscribe(customer, "active", trial_days=0)
    fetches: list[bool] = []

    def fetch(sid: str) -> dict[str, Any]:
        """What Stripe says: canceled once the customer's row is locked, as if a later event
        had overtaken this delivery while it waited. NOWAIT fails while it is held."""
        try:
            with factory() as other:
                other.scalars(select(Subscription).with_for_update(nowait=True)).one()
            fetches.append(False)
            return stripe_fake.subs[sid]
        except OperationalError:
            fetches.append(True)
            return stripe_fake.subs[sid] | {"status": "canceled"}

    stripe_fake.client.v1.subscriptions.retrieve.side_effect = fetch
    deliver(client, "customer.subscription.created", {"id": "sub_1", "object": "subscription"})
    assert fetches == [False, True]
    assert plan_of(factory) == "free"


def test_a_late_event_about_an_old_subscription_leaves_the_new_one(client, stripe_fake, factory):
    me = sign_up(client)
    subscribed(client, stripe_fake, me, status="active", trial_days=0)
    customer = stripe_fake.subs["sub_1"]["customer"]
    stripe_fake.subs["sub_1"]["status"] = "canceled"
    stripe_fake.subscribe(customer, "active", sid="sub_2", trial_days=0)
    deliver(client, "customer.subscription.created", {"id": "sub_2", "object": "subscription"})
    deliver(client, "customer.subscription.deleted", {"id": "sub_1", "object": "subscription"})
    assert plan_of(factory) == "pro"
    assert client.get("/api/billing").json()["subscription"]["status"] == "active"


@pytest.mark.parametrize(
    ("status", "plan"),
    [
        ("trialing", "pro"),
        ("active", "pro"),
        ("past_due", "pro"),
        ("canceled", "free"),
        ("unpaid", "free"),
        ("paused", "free"),
        ("incomplete", "free"),
        ("incomplete_expired", "free"),
    ],
)
def test_the_plan_follows_the_subscription_status(client, stripe_fake, factory, status, plan):
    me = sign_up(client)
    subscribed(client, stripe_fake, me)
    stripe_fake.subs["sub_1"]["status"] = status
    deliver(client, "customer.subscription.updated", {"id": "sub_1", "object": "subscription"})
    assert plan_of(factory) == plan


def test_cancelling_in_the_portal_sends_one_end_of_contract_confirmation(
    client, stripe_fake, factory, outbox
):
    me = sign_up(client)
    subscribed(client, stripe_fake, me, status="active", trial_days=0)
    stripe_fake.subs["sub_1"]["cancel_at_period_end"] = True
    for event_id in ("evt_a", "evt_b"):
        deliver(
            client,
            "customer.subscription.updated",
            {"id": "sub_1", "object": "subscription"},
            event_id,
        )
    assert outbox.subjects().count("Your Forgeway Pro subscription is cancelled") == 1
    assert plan_of(factory) == "pro"  # kept until the period ends
    status = client.get("/api/billing").json()["subscription"]
    assert status["cancelling"] is True and status["ends_at"] is not None


def test_trial_ending_payment_failed_and_renewal_reminders(client, stripe_fake, outbox):
    me = sign_up(client)
    subscribed(client, stripe_fake, me)
    deliver(
        client, "customer.subscription.trial_will_end", {"id": "sub_1", "object": "subscription"}
    )
    assert any(s.startswith("Your Forgeway Pro trial ends on") for s in outbox.subjects())

    stripe_fake.subs["sub_1"]["status"] = "past_due"
    stripe_fake.invoices["in_1"] = {
        "id": "in_1", "object": "invoice", "status": "open", "amount_paid": 0,
        "hosted_invoice_url": "https://invoice.stripe.com/i/in_1",
        "parent": {"subscription_details": {"subscription": "sub_1"}},
    }  # fmt: skip
    deliver(client, "invoice.payment_failed", {"id": "in_1", "object": "invoice"})
    failed = outbox.latest("ada@example.com")
    assert failed is not None and "https://invoice.stripe.com/i/in_1" in failed.text
    assert client.get("/api/billing").json()["subscription"]["status"] == "past_due"
    assert client.get("/api/auth/me").json()["plan"] == "pro"

    stripe_fake.subs["sub_1"]["status"] = "active"
    upcoming = {"object": "invoice", "parent": {"subscription_details": {"subscription": "sub_1"}}}
    deliver(client, "invoice.upcoming", upcoming, "evt_upcoming")
    assert any(s.startswith("Your Forgeway Pro subscription renews on") for s in outbox.subjects())


def test_no_renewal_reminder_for_a_monthly_plan(client, stripe_fake, outbox):
    me = sign_up(client)
    subscribed(client, stripe_fake, me, status="active", price="price_m", trial_days=0)
    upcoming = {"object": "invoice", "parent": {"subscription_details": {"subscription": "sub_1"}}}
    deliver(client, "invoice.upcoming", upcoming, "evt_upcoming")
    assert not any("renews" in s for s in outbox.subjects())


def test_the_webhook_is_rate_limited_per_ip(make_client, stripe_fake):
    client = make_client(make_billing(stripe_fake), billing_webhooks_per_minute=2)
    for n in range(2):
        assert deliver(client, "customer.created", {"id": f"c{n}"}).status_code == 200
    assert deliver(client, "customer.created", {"id": "c3"}).status_code == 429


# --- Portal, pause, withdrawal ---------------------------------------------------------------


def test_the_portal_opens_for_a_customer_only(client, stripe_fake):
    me = sign_up(client)
    assert client.post("/api/billing/portal", headers=csrf(me)).status_code == 404
    subscribed(client, stripe_fake, me)
    opened = client.post("/api/billing/portal", headers=csrf(me))
    assert opened.status_code == 200
    assert opened.json()["url"].startswith("https://billing.stripe.com/p/cus_")
    params = stripe_fake.client.v1.billing_portal.sessions.create.call_args.kwargs["params"]
    assert params["return_url"] == "https://forgeway.test/profile#billing"
    assert client.post("/api/billing/portal").status_code == 403  # CSRF


def test_pausing_returns_to_free_and_resuming_restores_pro(client, stripe_fake, factory):
    me = sign_up(client)
    subscribed(client, stripe_fake, me, status="active", trial_days=0)
    paused = client.post("/api/billing/pause", json={"months": 2}, headers=csrf(me))
    assert paused.status_code == 200, paused.text
    assert paused.json()["subscription"]["paused"] is True
    params = stripe_fake.client.v1.subscriptions.update.call_args.kwargs["params"]
    assert params["pause_collection"]["behavior"] == "void"
    resumes = datetime.fromtimestamp(params["pause_collection"]["resumes_at"], UTC)
    assert timedelta(days=59) < resumes - datetime.now(UTC) < timedelta(days=61)
    assert plan_of(factory) == "free"
    assert client.post("/api/billing/pause", json={}, headers=csrf(me)).status_code == 409
    resumed = client.post("/api/billing/resume", headers=csrf(me))
    assert resumed.json()["subscription"]["paused"] is False
    assert plan_of(factory) == "pro"


def test_managing_a_subscription_is_rate_limited_per_account(make_client, stripe_fake):
    client = make_client(make_billing(stripe_fake), billing_actions_per_hour=4)
    me = sign_up(client)
    subscribed(client, stripe_fake, me, status="active", trial_days=0)
    assert client.post("/api/billing/portal", headers=csrf(me)).status_code == 200
    assert client.post("/api/billing/pause", json={}, headers=csrf(me)).status_code == 200
    assert client.post("/api/billing/resume", headers=csrf(me)).status_code == 200
    assert client.post("/api/billing/withdraw", headers=csrf(me)).status_code == 409
    for path in ("portal", "resume", "withdraw"):
        limited = client.post(f"/api/billing/{path}", headers=csrf(me))
        assert (limited.status_code, limited.json()["code"]) == (429, "rate-limited")
    assert client.post("/api/billing/pause", json={}, headers=csrf(me)).status_code == 429


def test_a_trial_cannot_be_paused(client, stripe_fake):
    me = sign_up(client)
    subscribed(client, stripe_fake, me)
    assert client.post("/api/billing/pause", json={}, headers=csrf(me)).status_code == 409


def eu(factory) -> None:
    with transaction(factory) as session:
        session.scalars(select(Subscription)).one().country = "IE"


def test_an_eu_customer_can_withdraw_within_14_days(client, stripe_fake, factory, outbox):
    me = sign_up(client)
    subscribed(client, stripe_fake, me, status="active", trial_days=0, latest_invoice="in_9")
    stripe_fake.paid("in_9", 1900)
    assert client.get("/api/billing").json()["subscription"]["withdrawal_until"] is None  # GB
    refused = client.post("/api/billing/withdraw", headers=csrf(me))
    assert refused.status_code == 409
    eu(factory)
    assert client.get("/api/billing").json()["subscription"]["withdrawal_until"] is not None
    done = client.post("/api/billing/withdraw", headers=csrf(me))
    assert done.status_code == 200, done.text
    assert done.json()["subscription"]["status"] == "canceled"
    stripe_fake.client.v1.subscriptions.cancel.assert_called_once_with("sub_1")
    refund = stripe_fake.client.v1.credit_notes.create.call_args.kwargs["params"]
    assert (refund["invoice"], refund["refund_amount"]) == ("in_9", 1900)
    assert plan_of(factory) == "free"
    assert "You have withdrawn from your Forgeway Pro contract" in outbox.subjects()
    # The deletion webhook that follows sends no second confirmation.
    deliver(client, "customer.subscription.deleted", {"id": "sub_1", "object": "subscription"})
    assert not any("is cancelled" in s for s in outbox.subjects())


def test_a_withdrawal_refunds_every_payment_in_the_period_and_only_then_cancels(
    client, stripe_fake, factory, outbox
):
    me = sign_up(client)
    started = NOW - DAY * 3
    subscribed(client, stripe_fake, me, status="active", trial_days=0, started=started)
    eu(factory)
    stripe_fake.paid("in_first", 1900, started)  # the plan's payment
    stripe_fake.paid("in_switch", 700, NOW)  # the latest: only a proration after a plan switch
    stripe_fake.paid("in_old", 1900, started - DAY)  # before the period: kept
    stripe_fake.paid("in_other", 1900, sid="sub_other")  # another subscription's: kept
    order = MagicMock()
    order.attach_mock(stripe_fake.client.v1.credit_notes.create, "refund")
    order.attach_mock(stripe_fake.client.v1.subscriptions.cancel, "cancel")
    assert client.post("/api/billing/withdraw", headers=csrf(me)).status_code == 200
    assert [name for name, _, _ in order.mock_calls] == ["refund", "refund", "cancel"]
    refunds = stripe_fake.client.v1.credit_notes.create.call_args_list
    assert [
        (c.kwargs["params"]["invoice"], c.kwargs["params"]["refund_amount"]) for c in refunds
    ] == [
        ("in_first", 1900),
        ("in_switch", 700),
    ]
    assert [c.kwargs["options"]["idempotency_key"] for c in refunds] == [
        "withdraw-in_first",
        "withdraw-in_switch",
    ]
    assert "£26" in outbox.latest("ada@example.com").text


def test_a_failed_refund_cancels_nothing_and_says_so(client, stripe_fake, factory, outbox):
    me = sign_up(client)
    subscribed(client, stripe_fake, me, status="active", trial_days=0)
    eu(factory)
    stripe_fake.paid("in_9", 1900)
    stripe_fake.client.v1.credit_notes.create.side_effect = RuntimeError("stripe is down")
    refused = client.post("/api/billing/withdraw", headers=csrf(me))
    assert refused.status_code == 503 and refused.json()["code"] == "billing-unavailable"
    assert "has not been cancelled" in refused.json()["detail"]
    stripe_fake.client.v1.subscriptions.cancel.assert_not_called()
    assert plan_of(factory) == "pro"
    assert not any("withdraw" in s for s in outbox.subjects())


def test_a_failed_cancel_after_a_refund_is_recorded_logged_and_emailed(
    client, stripe_fake, factory, outbox, caplog
):
    me = sign_up(client)
    subscribed(client, stripe_fake, me, status="active", trial_days=0)
    eu(factory)
    stripe_fake.paid("in_9", 1900)
    stripe_fake.client.v1.subscriptions.cancel.side_effect = RuntimeError("stripe is down")
    done = client.post("/api/billing/withdraw", headers=csrf(me))
    assert done.status_code == 200, done.text
    with factory() as session:
        assert session.scalars(select(Subscription)).one().withdrawal_cancel_failed_at is not None
    assert any(
        r.levelno == logging.ERROR and "BILLING WITHDRAWAL NOT CANCELLED" in r.getMessage()
        for r in caplog.records
    )
    message = outbox.latest("ada@example.com")
    assert message is not None and message.subject == (
        "Your withdrawal from Forgeway Pro is being processed"
    )
    assert "£19" in message.text and "processing" in message.text
    # Trying again, once Stripe is back, finishes it without refunding twice over a new key.
    stripe_fake.client.v1.subscriptions.cancel.side_effect = stripe_fake._cancel
    assert client.post("/api/billing/withdraw", headers=csrf(me)).status_code == 200
    keys = {
        c.kwargs["options"]["idempotency_key"]
        for c in stripe_fake.client.v1.credit_notes.create.call_args_list
    }
    assert keys == {"withdraw-in_9"}
    with factory() as session:
        assert session.scalars(select(Subscription)).one().withdrawal_cancel_failed_at is None
    assert plan_of(factory) == "free"


def test_the_withdrawal_email_goes_after_the_commit_with_no_lock_held(
    client, stripe_fake, factory, outbox
):
    me = sign_up(client)
    subscribed(client, stripe_fake, me, status="active", trial_days=0)
    eu(factory)
    seen: list[tuple[str | None, str | None]] = []
    outbox.send = lambda _message: seen.append(_committed_status(factory))  # type: ignore[method-assign]
    assert client.post("/api/billing/withdraw", headers=csrf(me)).status_code == 200
    assert seen == [("canceled", "free")]


def _committed_status(factory) -> tuple[str | None, str | None]:
    """The row as another connection sees it; NOWAIT raises if a lock is still held on it."""
    with factory() as session:
        row = session.scalars(select(Subscription).with_for_update(nowait=True)).one()
        return row.status, session.get(User, row.user_id).plan


def test_account_emails_go_after_the_commit(make_client, factory, outbox):
    """Registering, a fresh link, an address change and a reset: each email names a token already
    committed, and no row of the account is locked while it is sent."""
    client = make_client()
    seen: list[tuple[str, int]] = []
    send = outbox.send

    def checking(message: EmailMessage) -> None:
        with factory() as session:
            user = session.scalars(
                select(User).where(User.email == "ada@example.com").with_for_update(nowait=True)
            ).one()
            tokens = session.scalar(
                select(func.count())
                .select_from(AccountToken)
                .where(AccountToken.user_id == user.id)
            )
        seen.append((message.subject, tokens or 0))
        send(message)

    outbox.send = checking  # type: ignore[method-assign]
    me = sign_up(client, verified=False)
    assert client.post("/api/auth/verify-email/resend", headers=csrf(me)).status_code == 202
    assert (
        client.post("/api/auth/password-reset", json={"email": "ada@example.com"}).status_code
        == 202
    )
    changed = client.put(
        "/api/auth/email",
        json={"email": "ada2@example.com", "password": "correct horse battery"},
        headers=csrf(me),
    )
    assert changed.status_code == 202, changed.text
    assert changed.json()["pending_email"] == "ada2@example.com"
    assert len(seen) == 4
    assert all(tokens >= 1 for _, tokens in seen)


def test_after_14_days_there_is_no_withdrawal(client, stripe_fake, factory):
    me = sign_up(client)
    subscribed(client, stripe_fake, me, status="active", trial_days=0, started=NOW - DAY * 15)
    eu(factory)
    assert client.get("/api/billing").json()["subscription"]["withdrawal_until"] is None
    assert client.post("/api/billing/withdraw", headers=csrf(me)).status_code == 409


def test_deleting_the_account_ends_the_subscription(client, stripe_fake):
    me = sign_up(client)
    subscribed(client, stripe_fake, me, status="active", trial_days=0)
    deleted = client.post(
        "/api/account/delete", json={"password": "correct horse battery"}, headers=csrf(me)
    )
    assert deleted.status_code == 204
    stripe_fake.client.v1.subscriptions.cancel.assert_called_once_with("sub_1")


def test_the_rows_are_gone_before_stripe_is_called_and_stay_gone_if_it_fails(
    client, stripe_fake, factory, caplog
):
    me = sign_up(client)
    subscribed(client, stripe_fake, me, status="active", trial_days=0)
    users_left: list[int | None] = []

    def fail(_sid: str) -> None:
        with factory() as session:
            users_left.append(session.scalar(select(func.count()).select_from(User)))
        raise RuntimeError("stripe is down")

    stripe_fake.client.v1.subscriptions.cancel.side_effect = fail
    deleted = client.post(
        "/api/account/delete", json={"password": "correct horse battery"}, headers=csrf(me)
    )
    assert deleted.status_code == 204
    assert users_left == [0]
    assert any(
        r.levelno == logging.ERROR and "BILLING DELETION NOT CANCELLED" in r.getMessage()
        for r in caplog.records
    )
    with factory() as session:
        # The id the owner needs is on the pseudonymised consent record.
        assert session.scalars(select(BillingConsent)).one().stripe_subscription_id == "sub_1"


def test_a_wrong_password_neither_deletes_nor_cancels(client, stripe_fake):
    me = sign_up(client)
    subscribed(client, stripe_fake, me, status="active", trial_days=0)
    refused = client.post("/api/account/delete", json={"password": "wrong"}, headers=csrf(me))
    assert refused.status_code == 422
    stripe_fake.client.v1.subscriptions.cancel.assert_not_called()


# --- Onboarding ------------------------------------------------------------------------------


def test_the_day_3_nudge_goes_once_to_a_trial_with_nothing_done(client, stripe_fake, factory):
    me = sign_up(client)
    subscribed(client, stripe_fake, me, started=NOW - DAY * 3 - timedelta(hours=1))
    with transaction(factory) as session:
        first = billing_app.onboarding_nudges(session, "https://forgeway.test")
    with transaction(factory) as session:
        second = billing_app.onboarding_nudges(session, "https://forgeway.test")
    assert [m.to for m in first] == ["ada@example.com"] and second == []


def test_no_nudge_once_an_exercise_is_passed_or_before_day_3(client, stripe_fake, factory):
    me = sign_up(client)
    subscribed(client, stripe_fake, me, started=NOW - DAY * 4)
    with transaction(factory) as session:
        user = session.scalars(select(User)).one()
        session.add(
            ExerciseProgress(user_id=user.id, exercise_id="starter.one", first_passed_at=NOW)
        )
    with transaction(factory) as session:
        assert billing_app.onboarding_nudges(session, "https://forgeway.test") == []
        status = billing_app.onboarding(session, user.id, NOW - DAY * 4)
        assert status.first_pass_at is not None and status.first_live_run_at is None
    with transaction(factory) as session:
        session.scalars(select(Subscription)).one().started_at = NOW - DAY
        session.execute(ExerciseProgress.__table__.delete())
    with transaction(factory) as session:
        assert billing_app.onboarding_nudges(session, "https://forgeway.test") == []


def reconcile_all(factory, billing: Billing) -> tuple[list[str], list[EmailMessage]]:
    with transaction(factory) as session:
        ids = billing_app.subscriptions_to_reconcile(session)
    messages: list[EmailMessage] = []
    for sid in ids:
        with transaction(factory) as session:
            messages += billing_app.reconcile(session, billing, sid)
    return ids, messages


def test_reconciling_recovers_a_lost_cancellation_webhook(client, stripe_fake, factory):
    me = sign_up(client)
    subscribed(client, stripe_fake, me, status="active", trial_days=0)
    stripe_fake.subs["sub_1"]["status"] = "canceled"  # the webhook never arrives
    ids, messages = reconcile_all(factory, make_billing(stripe_fake))
    assert ids == ["sub_1"]
    assert plan_of(factory) == "free"
    assert [m.to for m in messages] == ["ada@example.com"]
    # Ended now, so it is not re-fetched again, and nobody is told twice.
    assert reconcile_all(factory, make_billing(stripe_fake)) == ([], [])


def test_reconciling_moves_a_trial_past_its_end_on_to_what_stripe_says(
    client, stripe_fake, factory
):
    me = sign_up(client)
    subscribed(client, stripe_fake, me, started=NOW - DAY * 8)  # trial_end a day ago
    with transaction(factory) as session:
        row = session.scalars(select(Subscription)).one()
        assert row.status == "trialing"
        assert row.trial_end is not None
        assert row.trial_end < NOW
    stripe_fake.subs["sub_1"]["status"] = "active"
    ids, messages = reconcile_all(factory, make_billing(stripe_fake))
    assert ids == ["sub_1"] and messages == []
    with transaction(factory) as session:
        assert session.scalars(select(Subscription)).one().status == "active"
    assert plan_of(factory) == "pro"


def test_reconcile_finds_a_stale_trial_even_if_trialing_stopped_counting_as_live(
    client, stripe_fake, factory, monkeypatch
):
    me = sign_up(client)
    subscribed(client, stripe_fake, me, started=NOW - DAY * 8)
    monkeypatch.setattr(billing_app, "LIVE_STATUSES", frozenset({"active"}))
    with transaction(factory) as session:
        assert billing_app.subscriptions_to_reconcile(session) == ["sub_1"]
        assert billing_app.subscriptions_to_reconcile(session, now=NOW - DAY * 2) == []


def test_the_reconcile_command_does_nothing_with_billing_off(monkeypatch):
    monkeypatch.setattr("lattice.api.routes.billing.build_billing", lambda _settings: None)
    result = CliRunner().invoke(cli_app, ["billing", "reconcile"])
    assert result.exit_code == 0 and "billing is off" in result.output


def test_the_reconcile_command_carries_on_past_a_stripe_error_and_exits_1(
    client, stripe_fake, factory, engine, outbox, monkeypatch
):
    me = sign_up(client)
    subscribed(client, stripe_fake, me, status="active", trial_days=0)
    stripe_fake.subs["sub_1"]["status"] = "canceled"
    monkeypatch.setattr("lattice.cli.get_engine", lambda: engine)
    monkeypatch.setattr(
        "lattice.api.routes.billing.build_billing", lambda _settings: make_billing(stripe_fake)
    )
    monkeypatch.setattr("lattice.infrastructure.email.build_sender", lambda *_: outbox)
    # The first one is gone from the fake, so its fetch raises; the second must still be applied.
    monkeypatch.setattr(
        billing_app, "subscriptions_to_reconcile", lambda _session: ["sub_gone", "sub_1"]
    )
    result = CliRunner().invoke(cli_app, ["billing", "reconcile"])
    assert result.exit_code == 1
    assert plan_of(factory) == "free"
    assert outbox.latest("ada@example.com") is not None


def test_the_reconcile_command_finishes_a_withdrawal_whose_cancel_failed(
    client, stripe_fake, factory, engine, outbox, caplog, monkeypatch
):
    me = sign_up(client)
    subscribed(client, stripe_fake, me, status="active", trial_days=0)
    eu(factory)
    stripe_fake.paid("in_9", 1900)
    cancel = stripe_fake.client.v1.subscriptions.cancel
    cancel.side_effect = RuntimeError("stripe is down")
    assert client.post("/api/billing/withdraw", headers=csrf(me)).status_code == 200
    monkeypatch.setattr("lattice.cli.get_engine", lambda: engine)
    monkeypatch.setattr(
        "lattice.api.routes.billing.build_billing", lambda _settings: make_billing(stripe_fake)
    )
    monkeypatch.setattr("lattice.infrastructure.email.build_sender", lambda *_: outbox)

    def failed_at():
        with factory() as session:
            return session.scalars(select(Subscription)).one().withdrawal_cancel_failed_at

    # Stripe still refuses: the record stays, it is logged at ERROR, and the command exits 1.
    caplog.clear()
    assert CliRunner().invoke(cli_app, ["billing", "reconcile"]).exit_code == 1
    assert failed_at() is not None
    assert any(
        r.levelno == logging.ERROR and "BILLING WITHDRAWAL NOT CANCELLED" in r.getMessage()
        for r in caplog.records
    )
    # Stripe is back: cancelled, cleared, and the promised email goes.
    cancel.side_effect = stripe_fake._cancel
    assert CliRunner().invoke(cli_app, ["billing", "reconcile"]).exit_code == 0
    assert failed_at() is None
    assert plan_of(factory) == "free"
    last = outbox.latest("ada@example.com")
    assert last is not None and "being processed" not in last.subject
    # The next run has nothing left to retry.
    cancel.reset_mock()
    assert CliRunner().invoke(cli_app, ["billing", "reconcile"]).exit_code == 0
    cancel.assert_not_called()


def test_retrying_a_cancel_the_owner_already_made_only_records_it(client, stripe_fake, factory):
    me = sign_up(client)
    subscribed(client, stripe_fake, me, status="active", trial_days=0)
    with transaction(factory) as session:
        session.scalars(select(Subscription)).one().withdrawal_cancel_failed_at = NOW
    stripe_fake.subs["sub_1"]["status"] = "canceled"  # cancelled by hand in the dashboard
    with transaction(factory) as session:
        assert billing_app.failed_withdrawal_cancels(session) == ["sub_1"]
        billing_app.retry_withdrawal_cancel(session, make_billing(stripe_fake), "sub_1")
    stripe_fake.client.v1.subscriptions.cancel.assert_not_called()
    with factory() as session:
        assert session.scalars(select(Subscription)).one().withdrawal_cancel_failed_at is None
    assert plan_of(factory) == "free"
