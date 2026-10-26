"""Safe public sign-up over HTTP: verification, password reset, Turnstile, limits and purging."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update

from lattice.api.app import create_app
from lattice.application import accounts, rate_limits
from lattice.application.content_sync import sync_content
from lattice.infrastructure.db.engine import transaction
from lattice.infrastructure.db.models import AccountToken, Attempt, RateLimitHit, User
from lattice.infrastructure.turnstile import TurnstileVerifier
from lattice.settings import Settings
from tests.integration.test_api import ORIGIN, emailed_token, sign_up
from tests.integration.test_learning_flow import WRONG

PASSWORD = "correct horse battery"
# Cloudflare's documented test secrets.
ALWAYS_PASSES = "1x0000000000000000000000000000000AA"
ALWAYS_FAILS = "2x0000000000000000000000000000000AA"

MakeClient = Callable[..., TestClient]


@pytest.fixture
def make_client(engine, factory, catalogue, tmp_path) -> Iterator[MakeClient]:
    """Build clients on demand, each its own app (as separate API processes would be)."""
    with transaction(factory) as session:
        sync_content(session, catalogue.graph)
    opened: list[TestClient] = []

    def make(peer: str = "testclient", turnstile: TurnstileVerifier | None = None, **overrides):
        settings = Settings(
            content_dir=tmp_path,
            database_url=str(engine.url),
            allowed_origins="",
            log_level="WARNING",
            public_base_url="https://forgeway.example",
            **overrides,
        )
        client = TestClient(
            create_app(settings, engine=engine, turnstile=turnstile),
            headers={"origin": ORIGIN},
            client=(peer, 50000),
        )
        client.__enter__()
        opened.append(client)
        return client

    yield make
    for client in opened:
        client.__exit__(None, None, None)


@pytest.fixture
def client(make_client) -> TestClient:
    return make_client()


def csrf(me: dict) -> dict[str, str]:
    return {"x-csrf-token": me["csrf_token"]}


def register(client: TestClient, email: str = "ada@example.com", **extra: Any):
    return client.post(
        "/api/auth/register",
        json={"email": email, "password": PASSWORD, "display_name": "Ada", **extra},
    )


# Email verification -------------------------------------------------------------------------


def test_a_new_account_is_unverified_and_gets_a_link(client):
    me = register(client).json()
    assert me["email_verified"] is False and me["pending_email"] is None
    message = client.app.state.lattice.email.latest("ada@example.com")
    assert "https://forgeway.example/verify-email?token=" in message.text
    assert "24 hours" in message.text


def test_unverified_learners_cannot_submit_or_publish(client):
    me = register(client).json()
    response = client.post(
        "/api/exercises/starter.one/attempts", json={"files": WRONG}, headers=csrf(me)
    )
    assert response.status_code == 403
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["code"] == "email-unverified"
    published = client.patch(
        "/api/certificates/anything", json={"is_public": True}, headers=csrf(me)
    )
    assert published.json()["code"] == "email-unverified"
    # Exploring still works.
    assert client.get("/api/map").status_code == 200


def test_a_verification_link_works_once(client):
    register(client)
    token = emailed_token(client, "ada@example.com")
    assert client.post("/api/auth/verify-email", json={"token": token}).status_code == 204
    assert client.get("/api/auth/me").json()["email_verified"] is True
    again = client.post("/api/auth/verify-email", json={"token": token})
    assert again.status_code == 422 and "invalid or has expired" in again.json()["detail"]


def test_tokens_are_stored_hashed(client, factory):
    register(client)
    token = emailed_token(client, "ada@example.com")
    with factory() as session:
        row = session.scalars(select(AccountToken)).one()
    assert row.token_hash != token and len(row.token_hash) == 64
    assert row.expires_at - row.created_at == timedelta(hours=24)


def test_an_expired_verification_link_is_refused(client, factory):
    register(client)
    token = emailed_token(client, "ada@example.com")
    with transaction(factory) as session:
        session.execute(update(AccountToken).values(expires_at=datetime.now(UTC)))
    assert client.post("/api/auth/verify-email", json={"token": token}).status_code == 422


def test_resending_replaces_the_link_and_is_rate_limited(make_client):
    client = make_client(verification_emails_per_hour=2)
    me = register(client).json()
    first = emailed_token(client, "ada@example.com")
    for _ in range(2):
        assert client.post("/api/auth/verify-email/resend", headers=csrf(me)).status_code == 202
    limited = client.post("/api/auth/verify-email/resend", headers=csrf(me))
    assert limited.status_code == 429 and limited.json()["code"] == "rate-limited"
    assert client.post("/api/auth/verify-email", json={"token": first}).status_code == 422
    latest = emailed_token(client, "ada@example.com")
    assert client.post("/api/auth/verify-email", json={"token": latest}).status_code == 204
    done = client.post("/api/auth/verify-email/resend", headers=csrf(me))
    assert done.status_code == 409


def test_changing_email_takes_effect_only_once_the_new_address_is_verified(client):
    me = sign_up(client)
    wrong = client.put(
        "/api/auth/email", json={"email": "new@example.com", "password": "nope"}, headers=csrf(me)
    )
    assert wrong.status_code == 401
    changed = client.put(
        "/api/auth/email", json={"email": "New@Example.com", "password": PASSWORD}, headers=csrf(me)
    )
    assert changed.status_code == 202
    assert (changed.json()["email"], changed.json()["pending_email"]) == (
        "ada@example.com",
        "new@example.com",
    )
    token = emailed_token(client, "new@example.com")
    assert client.post("/api/auth/verify-email", json={"token": token}).status_code == 204
    after = client.get("/api/auth/me").json()
    assert (after["email"], after["pending_email"], after["email_verified"]) == (
        "new@example.com",
        None,
        True,
    )


def test_a_link_for_an_abandoned_address_change_is_refused(client):
    me = sign_up(client)
    for address in ("one@example.com", "two@example.com"):
        client.put(
            "/api/auth/email", json={"email": address, "password": PASSWORD}, headers=csrf(me)
        )
    stale = emailed_token(client, "one@example.com")
    assert client.post("/api/auth/verify-email", json={"token": stale}).status_code == 422
    assert client.get("/api/auth/me").json()["email"] == "ada@example.com"


def test_an_address_change_cannot_take_an_existing_account(client):
    sign_up(client, "grace@example.com")
    client.cookies.clear()
    me = sign_up(client)
    taken = client.put(
        "/api/auth/email",
        json={"email": "grace@example.com", "password": PASSWORD},
        headers=csrf(me),
    )
    assert taken.status_code == 409


# Password reset -----------------------------------------------------------------------------


def test_reset_requests_answer_the_same_whether_or_not_the_account_exists(client):
    sign_up(client)
    known = client.post("/api/auth/password-reset", json={"email": "ada@example.com"})
    unknown = client.post("/api/auth/password-reset", json={"email": "nobody@example.com"})
    assert known.status_code == unknown.status_code == 202
    assert known.content == unknown.content
    email = client.app.state.lattice.email
    assert email.latest("nobody@example.com") is None
    message = email.latest("ada@example.com")
    assert "/reset-password?token=" in message.text and "15 minutes" in message.text


def test_a_reset_sets_the_password_once_and_ends_every_session(make_client):
    first, second = make_client(), make_client()
    sign_up(first)
    second.post("/api/auth/login", json={"email": "ada@example.com", "password": PASSWORD})
    assert second.get("/api/auth/me").status_code == 200
    first.post("/api/auth/password-reset", json={"email": "ada@example.com"})
    token = emailed_token(first, "ada@example.com")
    new = "a much better passphrase"
    done = first.post("/api/auth/password-reset/confirm", json={"token": token, "password": new})
    assert done.status_code == 204
    assert first.get("/api/auth/me").status_code == 401
    assert second.get("/api/auth/me").status_code == 401
    old = first.post("/api/auth/login", json={"email": "ada@example.com", "password": PASSWORD})
    assert old.status_code == 401
    ok = first.post("/api/auth/login", json={"email": "ada@example.com", "password": new})
    assert ok.status_code == 200
    reused = first.post(
        "/api/auth/password-reset/confirm", json={"token": token, "password": "yet another one"}
    )
    assert reused.status_code == 422


def test_a_reset_link_can_be_checked_without_using_it(client, factory):
    sign_up(client)
    client.post("/api/auth/password-reset", json={"email": "ada@example.com"})
    token = emailed_token(client, "ada@example.com")

    def check(value: str) -> int:
        return client.post("/api/auth/password-reset/check", json={"token": value}).status_code

    assert check(token) == 204
    assert check(token) == 204  # checking does not consume it
    assert check("not-a-token") == 422
    with transaction(factory) as session:
        session.scalars(select(AccountToken)).one().expires_at = datetime.now(UTC)
    assert check(token) == 422


def test_a_verification_token_does_not_pass_the_reset_check(client):
    register(client)
    token = emailed_token(client, "ada@example.com")
    response = client.post("/api/auth/password-reset/check", json={"token": token})
    assert response.status_code == 422


def test_a_reset_link_expires_after_15_minutes(client, factory):
    sign_up(client)
    client.post("/api/auth/password-reset", json={"email": "ada@example.com"})
    token = emailed_token(client, "ada@example.com")
    with transaction(factory) as session:
        row = session.scalars(select(AccountToken)).one()
        assert row.expires_at - row.created_at == timedelta(minutes=15)
        row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    response = client.post(
        "/api/auth/password-reset/confirm", json={"token": token, "password": "a new passphrase"}
    )
    assert response.status_code == 422


def test_a_verification_token_cannot_reset_a_password(client):
    register(client)
    token = emailed_token(client, "ada@example.com")
    response = client.post(
        "/api/auth/password-reset/confirm", json={"token": token, "password": "a new passphrase"}
    )
    assert response.status_code == 422


def test_reset_requests_are_limited_per_email_and_per_ip(make_client):
    client = make_client(password_reset_per_email_per_hour=2, password_reset_per_ip_per_hour=4)

    def reset(email: str) -> int:
        return client.post("/api/auth/password-reset", json={"email": email}).status_code

    assert [reset("a@example.com") for _ in range(3)] == [202, 202, 429]
    # The IP is checked first, so the refused request still used one of its four.
    assert [reset("b@example.com"), reset("c@example.com")] == [202, 429]


# Turnstile ----------------------------------------------------------------------------------


def cloudflare(fields: dict[str, str]) -> dict[str, Any]:
    """A stand-in for siteverify that behaves as Cloudflare's test secrets do."""
    return {"success": fields["secret"] == ALWAYS_PASSES and bool(fields["response"])}


def test_turnstile_is_skipped_without_a_secret(client):
    assert client.app.state.lattice.turnstile is None
    assert register(client).status_code == 201


def test_turnstile_must_pass_when_on(make_client):
    passing = make_client(turnstile=TurnstileVerifier(ALWAYS_PASSES, cloudflare))
    missing = register(passing)
    assert missing.status_code == 403 and missing.json()["code"] == "challenge-failed"
    assert register(passing, turnstile_token="XXXX.DUMMY.TOKEN.XXXX").status_code == 201
    failing = make_client(turnstile=TurnstileVerifier(ALWAYS_FAILS, cloudflare))
    refused = register(failing, "b@example.com", turnstile_token="XXXX.DUMMY.TOKEN.XXXX")
    assert refused.status_code == 403


def test_turnstile_sends_the_client_ip_and_fails_closed():
    seen: list[dict[str, str]] = []

    def record(fields: dict[str, str]) -> dict[str, Any]:
        seen.append(fields)
        return {"success": True}

    assert TurnstileVerifier("s", record).verify("tok", "203.0.113.7")
    assert seen == [{"secret": "s", "response": "tok", "remoteip": "203.0.113.7"}]

    def unreachable(_: dict[str, str]) -> dict[str, Any]:
        raise OSError("no route")

    assert not TurnstileVerifier("s", unreachable).verify("tok", None)


def test_public_config_exposes_only_the_site_key(make_client):
    assert make_client().get("/api/config").json() == {
        "turnstile_site_key": None,
        "free_exercises_per_branch": 3,
    }
    on = make_client(turnstile_site_key="1x00000000000000000000AA", turnstile_secret="secret")
    assert on.get("/api/config").json()["turnstile_site_key"] == "1x00000000000000000000AA"


# Rate limits and the real client IP ---------------------------------------------------------


def test_registration_is_limited_per_ip_across_processes(make_client):
    one = make_client(peer="198.51.100.1", register_per_ip_per_hour=2)
    assert register(one, "a@example.com").status_code == 201
    one.cookies.clear()
    # A second app, as another API process or one after a restart, shares the count.
    two = make_client(peer="198.51.100.1", register_per_ip_per_hour=2)
    assert register(two, "b@example.com").status_code == 201
    two.cookies.clear()
    limited = register(two, "c@example.com")
    assert limited.status_code == 429 and limited.json()["code"] == "rate-limited"
    other_ip = make_client(peer="198.51.100.2", register_per_ip_per_hour=2)
    assert register(other_ip, "c@example.com").status_code == 201


def test_forwarding_headers_are_ignored_from_untrusted_peers(make_client):
    client = make_client(peer="198.51.100.1", register_per_ip_per_hour=1)
    assert (
        register(
            client,
            "a@example.com",
        ).status_code
        == 201
    )
    client.cookies.clear()
    spoofed = client.post(
        "/api/auth/register",
        json={"email": "b@example.com", "password": PASSWORD, "display_name": "B"},
        headers={"cf-connecting-ip": "203.0.113.9", "x-forwarded-for": "203.0.113.9"},
    )
    assert spoofed.status_code == 429


def test_trusted_proxies_pass_on_the_client_ip(make_client, factory):
    proxy = make_client(
        peer="172.18.0.5", trusted_proxies="172.16.0.0/12", register_per_ip_per_hour=1
    )
    for n, headers in enumerate(
        ({"cf-connecting-ip": "203.0.113.1"}, {"x-forwarded-for": "203.0.113.2, 172.18.0.1"})
    ):
        response = proxy.post(
            "/api/auth/register",
            json={"email": f"{n}@example.com", "password": PASSWORD, "display_name": "B"},
            headers=headers,
        )
        assert response.status_code == 201
        proxy.cookies.clear()
    with factory() as session:
        keys = set(session.scalars(select(RateLimitHit.key)))
    assert keys == {"register:ip:203.0.113.1", "register:ip:203.0.113.2"}


def test_failed_sign_ins_still_count(make_client):
    client = make_client(peer="198.51.100.1", login_per_ip_per_hour=3)
    sign_up(client)
    client.cookies.clear()
    for _ in range(3):
        wrong = client.post("/api/auth/login", json={"email": "ada@example.com", "password": "x"})
        assert wrong.status_code == 401
    limited = client.post(
        "/api/auth/login", json={"email": "ada@example.com", "password": PASSWORD}
    )
    assert limited.status_code == 429


def test_sign_in_is_limited_per_email_whatever_the_ip(make_client, factory):
    sign_up(make_client(peer="198.51.100.1"))
    for peer in ("198.51.100.2", "198.51.100.3"):
        client = make_client(peer=peer, login_per_email_per_hour=2)
        wrong = client.post("/api/auth/login", json={"email": "ADA@example.com", "password": "x"})
        assert wrong.status_code == 401
    fresh_ip = make_client(peer="198.51.100.4", login_per_email_per_hour=2)
    limited = fresh_ip.post(
        "/api/auth/login", json={"email": "ada@example.com", "password": PASSWORD}
    )
    assert limited.status_code == 429 and limited.json()["code"] == "rate-limited"
    other = fresh_ip.post("/api/auth/login", json={"email": "bob@example.com", "password": "x"})
    assert other.status_code == 401  # another address is not affected
    with factory() as session:
        keys = set(session.scalars(select(RateLimitHit.key)))
    assert "login:email:ada@example.com" in keys


def test_rate_limit_hits_age_out(factory):
    now = datetime.now(UTC)
    hour = timedelta(hours=1)
    with transaction(factory) as session:
        assert rate_limits.consume(session, "k", limit=1, window=hour, now=now - 2 * hour)
        assert rate_limits.consume(session, "k", limit=1, window=hour, now=now)
        assert not rate_limits.consume(session, "k", limit=1, window=hour, now=now)
        session.add(RateLimitHit(key="old", at=now - timedelta(days=2)))
    with transaction(factory) as session:
        assert rate_limits.prune(session, now) == 1


# Caps on grading ----------------------------------------------------------------------------


def test_a_full_queue_answers_503_with_retry_after(make_client):
    client = make_client(max_queue_depth=1)
    me = sign_up(client)
    first = client.post(
        "/api/exercises/starter.one/attempts", json={"files": WRONG}, headers=csrf(me)
    )
    assert first.status_code == 202
    client.cookies.clear()
    other = sign_up(client, "grace@example.com")
    busy = client.post(
        "/api/exercises/starter.one/attempts", json={"files": WRONG}, headers=csrf(other)
    )
    assert busy.status_code == 503
    assert busy.headers["retry-after"] == "60"
    assert busy.json()["code"] == "busy"


def test_a_second_attempt_in_flight_is_a_conflict(client):
    me = sign_up(client)
    for expected in (202, 409):
        response = client.post(
            "/api/exercises/starter.one/attempts", json={"files": WRONG}, headers=csrf(me)
        )
        assert response.status_code == expected
    assert response.json()["code"] == "attempt-in-flight"


def test_the_daily_caps_answer_with_their_own_problem_codes(make_client, factory):
    client = make_client(attempts_per_day=1, grading_seconds_per_day=60)
    me = sign_up(client)

    def submit():
        return client.post(
            "/api/exercises/starter.one/attempts", json={"files": WRONG}, headers=csrf(me)
        )

    assert submit().status_code == 202
    with transaction(factory) as session:  # graded, and it ran into its time limit
        session.execute(
            update(Attempt).values(
                status="failed", report={"status": "failed", "duration_ms": 70_000}
            )
        )
    capped = submit()
    assert capped.status_code == 429
    assert capped.headers["content-type"] == "application/problem+json"
    assert (capped.json()["code"], capped.json()["limit"]) == ("attempt-daily-cap", 1)

    roomy = make_client(attempts_per_day=10, grading_seconds_per_day=60)
    roomy.cookies.update(client.cookies)
    spent = roomy.post(
        "/api/exercises/starter.one/attempts", json={"files": WRONG}, headers=csrf(me)
    )
    assert spent.status_code == 429
    assert (spent.json()["code"], spent.json()["budget_minutes"]) == ("grading-budget", 1)


# Purging and the test outbox ----------------------------------------------------------------


def test_unverified_accounts_are_purged_after_7_days(client, factory):
    register(client, "old@example.com")
    client.cookies.clear()
    register(client, "new@example.com")
    client.cookies.clear()
    sign_up(client, "kept@example.com")
    with transaction(factory) as session:
        session.execute(
            update(User)
            .where(User.email.in_(["old@example.com", "kept@example.com"]))
            .values(created_at=datetime.now(UTC) - timedelta(days=8))
        )
    for expected in (1, 0):  # idempotent
        with transaction(factory) as session:
            assert accounts.purge_unverified(session).accounts == expected
    with factory() as session:
        emails = set(session.scalars(select(User.email)))
    assert emails == {"new@example.com", "kept@example.com"}


def test_the_outbox_endpoint_exists_only_for_e2e_with_console_email(make_client):
    assert make_client().get("/api/test/outbox/latest?email=a@example.com").status_code == 404
    e2e = make_client(e2e=True)
    register(e2e)
    latest = e2e.get("/api/test/outbox/latest", params={"email": "ADA@example.com"})
    assert latest.status_code == 200
    assert latest.json()["token"] == emailed_token(e2e, "ada@example.com")
    with pytest.raises(ValueError, match="RESEND_API_KEY"):
        Settings(email_provider="resend", e2e=True)
    resend = Settings(email_provider="resend", resend_api_key="re_x", e2e=True)
    assert resend.email_outbox_exposed is False


def test_the_test_plan_endpoint_exists_only_for_e2e_with_console_email(make_client):
    body = {"email": "ADA@example.com", "plan": "pro"}
    assert make_client().post("/api/test/plan", json=body).status_code == 404
    e2e = make_client(e2e=True)
    register(e2e)
    assert e2e.post("/api/test/plan", json=body).status_code == 204
    assert e2e.get("/api/auth/me").json()["plan"] == "pro"
    assert e2e.post("/api/test/plan", json={**body, "email": "x@example.com"}).status_code == 404
