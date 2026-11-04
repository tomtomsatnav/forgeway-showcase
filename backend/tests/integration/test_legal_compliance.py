"""UK compliance behaviour (docs/legal/compliance-review-2026-11.md): the age check, recorded
terms acceptance, the marketing opt-out and its unsubscribe links, the waitlist's 12-month
retention, and regulation-37 consents that outlive the account, pseudonymised."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from lattice.application import marketing, retention
from lattice.application.accounts import TERMS_VERSION
from lattice.application.errors import InvalidInputError
from lattice.domain.email import EmailMessage
from lattice.infrastructure.db.engine import transaction
from lattice.infrastructure.db.models import (
    AccountToken,
    BillingConsent,
    LearnerProfile,
    ProWaitlistEntry,
    User,
)
from tests.integration.test_api import emailed_token, sign_up
from tests.integration.test_billing_api import (  # noqa: F401 - fixtures
    DAY,
    client,
    csrf,
    make_client,
    outbox,
    start,
    stripe_fake,
    subscribed,
)

PASSWORD = "correct horse battery"


@pytest.fixture
def api_client(make_client):  # noqa: F811
    """The app with billing off."""
    return make_client()


def _register(api_client, **body):
    return api_client.post(
        "/api/auth/register",
        json={"email": "ada@example.com", "password": PASSWORD, "display_name": "Ada"} | body,
    )


def _user(factory, email: str = "ada@example.com") -> User:
    with factory() as session:
        return session.scalars(select(User).where(User.email == email)).one()


def _profile(factory, email: str = "ada@example.com") -> LearnerProfile:
    with factory() as session:
        user = session.scalars(select(User).where(User.email == email)).one()
        profile = session.get(LearnerProfile, user.id)
        assert profile is not None
        return profile


# --- Age and terms ---------------------------------------------------------------------------


@pytest.mark.parametrize("body", [{}, {"over_18": False}])
def test_signing_up_needs_the_18_or_over_confirmation(api_client, factory, body):
    response = _register(api_client, **body)
    assert response.status_code == 422
    with factory() as session:
        assert session.scalars(select(User)).first() is None


def test_signing_up_records_the_terms_version_and_when(api_client, factory):
    before = datetime.now(UTC)
    response = _register(api_client, over_18=True)
    assert response.status_code == 201, response.text
    assert response.json()["terms_current"] is True
    user = _user(factory)
    assert user.terms_version == TERMS_VERSION
    assert user.terms_accepted_at is not None and user.terms_accepted_at >= before


def test_a_material_terms_change_asks_again_and_records_the_new_acceptance(
    api_client,
    factory,
):
    me = sign_up(api_client)
    with transaction(factory) as session:
        session.scalars(select(User)).one().terms_version = "2020-01-01"
    assert api_client.get("/api/auth/me").json()["terms_current"] is False
    stale = api_client.post("/api/auth/terms", json={"version": "2020-01-01"}, headers=csrf(me))
    assert stale.status_code == 422
    accepted = api_client.post("/api/auth/terms", json={"version": TERMS_VERSION}, headers=csrf(me))
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["terms_current"] is True
    assert _user(factory).terms_version == TERMS_VERSION


# --- Marketing opt-out -----------------------------------------------------------------------


def test_the_sign_up_opt_out_is_stored_and_the_profile_toggles_it(api_client, factory):
    response = _register(api_client, over_18=True, marketing_opt_out=True)
    assert response.json()["profile"]["marketing_opt_out"] is True
    assert _profile(factory).marketing_opt_out is True
    me = response.json()
    back_in = api_client.patch(
        "/api/auth/profile", json={"marketing_opt_out": False}, headers=csrf(me)
    )
    assert back_in.json()["profile"]["marketing_opt_out"] is False
    assert _profile(factory).marketing_opt_out is False


def test_customers_are_opted_in_unless_they_refuse(api_client, factory):
    assert _register(api_client, over_18=True).json()["profile"]["marketing_opt_out"] is False


def test_the_checkout_opt_out_is_stored(client, factory):  # noqa: F811
    me = sign_up(client)
    assert start(client, me, marketing_opt_out=True).status_code == 200
    assert _profile(factory).marketing_opt_out is True


def test_offers_go_only_to_verified_customers_who_have_not_opted_out(
    client,  # noqa: F811
    stripe_fake,  # noqa: F811
    factory,
):
    me = sign_up(client)
    with factory() as session:
        assert marketing.may_send_offers(session, session.get(User, me["id"])) is False
    subscribed(client, stripe_fake, me)
    with transaction(factory) as session:
        user = session.get(User, me["id"])
        assert user is not None
        assert marketing.may_send_offers(session, user) is True
        profile = session.get(LearnerProfile, user.id)
        assert profile is not None
        profile.marketing_opt_out = True
    with factory() as session:
        assert marketing.may_send_offers(session, session.get(User, me["id"])) is False


# --- Unsubscribe links -----------------------------------------------------------------------


def _token(link: str) -> str:
    return link.split("token=", 1)[1]


def test_every_marketing_email_carries_a_working_unsubscribe_link(api_client, factory):
    sign_up(api_client)
    with transaction(factory) as session:
        user = session.scalars(select(User)).one()
        message = marketing.with_unsubscribe(
            session, EmailMessage(user.email, "Offer", "Hello", "<p>Hello</p>"), user,
            "https://forgeway.test",
        )  # fmt: skip
    link = message.text.rsplit(" ", 1)[1]
    assert link.startswith("https://forgeway.test/unsubscribe?token=")
    assert "Unsubscribe from offers" in message.html and _token(link) in message.html
    done = api_client.post("/api/marketing/unsubscribe", json={"token": _token(link)})
    assert done.status_code == 204
    assert _profile(factory).marketing_opt_out is True
    again = api_client.post("/api/marketing/unsubscribe", json={"token": _token(link)})
    assert again.status_code == 204  # a second click is harmless


def test_unsubscribing_is_rate_limited_per_ip(api_client, monkeypatch):
    monkeypatch.setattr("lattice.api.routes.marketing.UNSUBSCRIBES_PER_IP_PER_HOUR", 1)
    body = {"token": "not-a-token"}
    assert api_client.post("/api/marketing/unsubscribe", json=body).status_code == 422
    assert api_client.post("/api/marketing/unsubscribe", json=body).status_code == 429


def test_an_unknown_unsubscribe_token_is_refused(api_client, factory):
    sign_up(api_client)
    response = api_client.post("/api/marketing/unsubscribe", json={"token": "not-a-token"})
    assert response.status_code == 422
    assert "profile" in response.json()["detail"]
    assert _profile(factory).marketing_opt_out is False


def test_an_expired_unsubscribe_token_is_refused(api_client, factory):
    sign_up(api_client)
    with transaction(factory) as session:
        user = session.scalars(select(User)).one()
        old = datetime.now(UTC) - marketing.UNSUBSCRIBE_TTL - DAY
        link = marketing.unsubscribe_link(session, user, "https://forgeway.test", now=old)
    response = api_client.post("/api/marketing/unsubscribe", json={"token": _token(link)})
    assert response.status_code == 422
    assert "expired" in response.json()["detail"]
    assert _profile(factory).marketing_opt_out is False


def test_a_verification_token_does_not_unsubscribe(api_client, factory):
    sign_up(api_client, verified=False)
    token = emailed_token(api_client, "ada@example.com")
    with transaction(factory) as session, pytest.raises(InvalidInputError):
        marketing.unsubscribe(session, token)
    assert _profile(factory).marketing_opt_out is False
    with factory() as session:
        assert session.scalars(select(AccountToken)).one().purpose == "verify-email"


# --- Waitlist retention ----------------------------------------------------------------------


def test_waitlist_entries_go_after_12_months(api_client, factory):
    old, new = sign_up(api_client, "old@example.com"), sign_up(api_client, "new@example.com")
    now = datetime.now(UTC)
    with transaction(factory) as session:
        for me, joined in ((old, now - timedelta(days=366)), (new, now - timedelta(days=300))):
            session.add(ProWaitlistEntry(user_id=me["id"], email="x@example.com", joined_at=joined))
    with transaction(factory) as session:
        summary = retention.purge_expired(session, now)
    assert summary.waitlist == 1
    with factory() as session:
        left = [str(row.user_id) for row in session.scalars(select(ProWaitlistEntry))]
    assert left == [new["id"]]


def test_deleting_the_account_removes_its_waitlist_entry(api_client, factory):
    me = sign_up(api_client)
    assert api_client.post("/api/pro/waitlist", json={}, headers=csrf(me)).status_code == 200
    deleted = api_client.post("/api/account/delete", json={"password": PASSWORD}, headers=csrf(me))
    assert deleted.status_code == 204
    with factory() as session:
        assert session.scalars(select(ProWaitlistEntry)).first() is None


# --- Consents outlive the account ------------------------------------------------------------


def test_deleting_the_account_keeps_its_consent_pseudonymised(client, stripe_fake, factory):  # noqa: F811
    me = sign_up(client)
    subscribed(client, stripe_fake, me, status="active", trial_days=0)
    with factory() as session:
        before = session.scalars(select(BillingConsent)).one()
    deleted = client.post("/api/account/delete", json={"password": PASSWORD}, headers=csrf(me))
    assert deleted.status_code == 204
    with factory() as session:
        assert session.scalars(select(User)).first() is None
        kept = session.scalars(select(BillingConsent)).one()
    assert kept.user_id is None
    assert (kept.created_at, kept.wording_version, kept.wording, kept.plan) == (
        before.created_at, before.wording_version, before.wording, before.plan,
    )  # fmt: skip
    assert kept.checkout_session_id == before.checkout_session_id
    assert kept.stripe_customer_id is not None and kept.stripe_customer_id.startswith("cus_")
    assert kept.stripe_subscription_id == "sub_1"
    assert "ada@example.com" not in kept.wording


def test_consents_go_after_six_years(api_client, factory):
    now = datetime.now(UTC)
    with transaction(factory) as session:
        for age in (timedelta(days=6 * 365 + 3), timedelta(days=5 * 365)):
            session.add(
                BillingConsent(
                    user_id=None, created_at=now - age, wording_version="v", wording="w",
                    plan="annual",
                )
            )  # fmt: skip
    with transaction(factory) as session:
        assert retention.purge_expired(session, now).consents == 1
    with factory() as session:
        assert len(session.scalars(select(BillingConsent)).all()) == 1


def test_expired_sessions_are_removed(api_client, factory):
    sign_up(api_client)
    later = datetime.now(UTC) + timedelta(days=15)
    with transaction(factory) as session:
        assert retention.purge_expired(session, datetime.now(UTC)).sessions == 0
    with transaction(factory) as session:
        assert retention.purge_expired(session, later).sessions == 1
