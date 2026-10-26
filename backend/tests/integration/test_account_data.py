"""A learner's own data over HTTP: the JSON export and account deletion."""

from __future__ import annotations

import json
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from lattice.api.app import create_app
from lattice.application.content_sync import sync_content
from lattice.infrastructure.db.engine import transaction
from lattice.infrastructure.db.models import Base, RateLimitHit, User
from lattice.settings import Settings
from tests.integration.test_api import ORIGIN, go_pro, sign_up
from tests.integration.test_certificates_api import complete_starter, csrf_of, publish
from tests.integration.test_progression_flow import catalogue  # noqa: F401

PASSWORD = "correct horse battery"  # what `sign_up` registers with


@pytest.fixture
def make_client(engine, factory, catalogue, tmp_path) -> Iterator:  # noqa: F811
    with transaction(factory) as session:
        sync_content(session, catalogue.graph)
    opened: list[TestClient] = []

    def make(**overrides) -> TestClient:
        settings = Settings(
            content_dir=tmp_path,
            database_url=str(engine.url),
            allowed_origins="",
            log_level="WARNING",
            public_base_url="https://forgeway.example",
            **overrides,
        )
        client = TestClient(create_app(settings, engine=engine), headers={"origin": ORIGIN})
        client.__enter__()
        opened.append(client)
        return client

    yield make
    for client in opened:
        client.__exit__(None, None, None)


@pytest.fixture
def client(make_client) -> TestClient:
    return make_client()


@pytest.fixture
def busy(client, factory, catalogue) -> dict:  # noqa: F811
    """A Pro learner with a completed starter branch, a public certificate and a waitlist
    entry: rows in nearly every table."""
    me = sign_up(client)
    go_pro(factory)
    complete_starter(client, factory, catalogue, me)
    (certificate,) = client.get("/api/certificates").json()["certificates"]
    publish(client, me, certificate)
    joined = client.post("/api/pro/waitlist", json={"plan": "team"}, headers=csrf_of(me))
    assert joined.status_code == 200, joined.text
    return {"me": me, "certificate": certificate}


def test_the_export_holds_everything_about_the_learner(client, busy):
    response = client.get("/api/account/export")
    assert response.status_code == 200, response.text
    assert response.headers["content-disposition"].startswith(
        'attachment; filename="forgeway-data-'
    )
    assert response.headers["cache-control"] == "no-store"
    data = response.json()
    assert data["format"] == "forgeway-account-export" and data["version"] == 1
    assert data["account"]["email"] == "ada@example.com"
    assert data["account"]["plan"] == "pro"
    assert data["profile"]["time_zone"]
    assert {a["exercise_id"] for a in data["attempts"]} == {"starter.one", "starter.two"}
    assert all("def add" in "".join(a["files"].values()) for a in data["attempts"])
    assert all(a["report"] for a in data["attempts"])
    assert sum(e["amount"] for e in data["xp_events"]) > 0
    assert data["badges"], "the first pass earns a badge"
    assert [c["id"] for c in data["certificates"]] == [busy["certificate"]["id"]]
    assert data["certificates"][0]["is_public"] is True
    assert data["waitlist"]["plan_interest"] == "team"
    assert len(data["sessions"]) == 1
    assert {r["purpose"] for r in data["emailed_links"]} <= {"verify-email", "reset-password"}
    assert any(r["key"].startswith("export:user:") for r in data["rate_limit_records"])


def test_the_export_leaves_out_secrets(client, busy):
    text = client.get("/api/account/export").text
    assert "argon2" not in text
    assert "token_hash" not in text and "csrf" not in text
    assert "password" not in json.loads(text)["account"]


def test_the_export_needs_a_session(make_client):
    client = make_client()
    response = client.get("/api/account/export")
    assert response.status_code == 401


def test_the_export_is_rate_limited(make_client):
    client = make_client(account_exports_per_hour=2)
    sign_up(client)
    for _ in range(2):
        assert client.get("/api/account/export").status_code == 200
    limited = client.get("/api/account/export")
    assert limited.status_code == 429 and limited.json()["code"] == "rate-limited"


def test_deleting_needs_the_current_password(client, busy, factory):
    wrong = client.post(
        "/api/account/delete", json={"password": "not my password"}, headers=csrf_of(busy["me"])
    )
    assert wrong.status_code == 422
    assert "has not been deleted" in wrong.json()["detail"]
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(User)) == 1


def test_deleting_needs_the_csrf_token(client, busy):
    response = client.post("/api/account/delete", json={"password": PASSWORD})
    assert response.status_code == 403


def test_deleting_removes_every_row_and_ends_every_session(make_client, busy, factory):
    client = make_client()
    other = make_client()  # a second browser signed in to the same account
    signed_in = other.post(
        "/api/auth/login", json={"email": "ada@example.com", "password": PASSWORD}
    )
    assert signed_in.status_code == 200
    me = client.post(
        "/api/auth/login", json={"email": "ada@example.com", "password": PASSWORD}
    ).json()
    # Someone else's rows stay.
    stranger = make_client()
    sign_up(stranger, "grace@example.com")

    response = client.post("/api/account/delete", json={"password": PASSWORD}, headers=csrf_of(me))
    assert response.status_code == 204, response.text
    assert 'lattice_session=""' in response.headers["set-cookie"]

    assert client.get("/api/auth/me").status_code == 401
    assert other.get("/api/auth/me").status_code == 401
    assert stranger.get("/api/auth/me").status_code == 200
    page = client.get(f"/c/{busy['certificate']['id']}")
    assert page.status_code == 404
    assert client.get(f"/api/public/certificates/{busy['certificate']['id']}").status_code == 404

    with factory() as session:
        (grace,) = session.scalars(select(User)).all()
        assert grace.email == "grace@example.com"
        for table in Base.metadata.sorted_tables:
            if "user_id" in table.c:
                owners = set(session.scalars(select(table.c.user_id)))
                assert owners <= {grace.id}, f"{table.name} still holds the deleted learner's rows"
        keys = list(session.scalars(select(RateLimitHit.key)))
        assert not [k for k in keys if k.endswith(":ada@example.com")]
    gone = client.post("/api/auth/login", json={"email": "ada@example.com", "password": PASSWORD})
    assert gone.status_code == 401


def test_deleting_is_rate_limited(make_client):
    client = make_client(account_deletions_per_hour=2)
    me = sign_up(client)
    for _ in range(2):
        wrong = client.post("/api/account/delete", json={"password": "nope"}, headers=csrf_of(me))
        assert wrong.status_code == 422
    limited = client.post("/api/account/delete", json={"password": PASSWORD}, headers=csrf_of(me))
    assert limited.status_code == 429


def test_a_rate_limit_key_for_a_similar_address_is_not_the_learners(client, factory):
    sign_up(client)
    with transaction(factory) as session:
        session.add(RateLimitHit(key="reset:email:bada@example.com"))
        session.add(RateLimitHit(key="reset:email:ada@example.com"))
    records = client.get("/api/account/export").json()["rate_limit_records"]
    keys = {r["key"] for r in records}
    assert "reset:email:ada@example.com" in keys
    assert "reset:email:bada@example.com" not in keys
