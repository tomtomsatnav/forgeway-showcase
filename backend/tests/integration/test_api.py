"""HTTP contract tests: the full journey through the API against a real database."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from lattice.api.app import create_app
from lattice.application import plans
from lattice.application.content_sync import sync_content
from lattice.domain.entitlements import Plan
from lattice.infrastructure.db.engine import transaction
from lattice.settings import Settings
from tests.integration.test_learning_flow import CORRECT, WRONG, run_worker_once

ORIGIN = "http://testserver"


@pytest.fixture
def client(engine, factory, catalogue, tmp_path) -> Iterator[TestClient]:
    with transaction(factory) as session:
        sync_content(session, catalogue.graph)
    settings = Settings(
        content_dir=tmp_path, database_url=str(engine.url), allowed_origins="", log_level="WARNING"
    )
    with TestClient(create_app(settings, engine=engine), headers={"origin": ORIGIN}) as client:
        yield client


def emailed_token(client: TestClient, email: str) -> str:
    """The token in the newest email the app sent to `email` (the console sender keeps them)."""
    message = client.app.state.lattice.email.latest(email)  # type: ignore[attr-defined]
    assert message is not None, f"no email to {email}"
    return message.text.split("token=", 1)[1].split()[0]


def sign_up(client: TestClient, email: str = "ada@example.com", *, verified: bool = True) -> dict:
    """Register (and by default verify the address, as following the emailed link does)."""
    response = client.post(
        "/api/auth/register",
        json={"email": email, "password": "correct horse battery", "display_name": "Ada"},
    )
    assert response.status_code == 201, response.text
    if not verified:
        return response.json()
    token = emailed_token(client, email)
    assert client.post("/api/auth/verify-email", json={"token": token}).status_code == 204
    return client.get("/api/auth/me").json()


def go_pro(factory, email: str = "ada@example.com") -> None:
    """Put an account on Pro, as `forgeway accounts set-plan` does (there is no billing)."""
    with transaction(factory) as session:
        plans.set_plan(session, email, Plan.PRO)


def test_health_and_readiness(client):
    assert client.get("/healthz").json() == {"status": "ok"}
    assert client.get("/readyz").json()["status"] == "ready"


def test_unauthenticated_requests_get_a_problem_response(client):
    response = client.get("/api/map")
    assert response.status_code == 401
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["code"] == "unauthenticated"


def test_validation_errors_name_the_field(client):
    response = client.post(
        "/api/auth/register", json={"email": "not-an-email", "password": "x", "display_name": ""}
    )
    assert response.status_code == 422
    assert response.json()["detail"].startswith("email:")


def test_register_keeps_the_theme_chosen_before_the_account_existed(client):
    response = client.post(
        "/api/auth/register",
        json={
            "email": "r@example.com",
            "password": "correct horse battery",
            "display_name": "R",
            "mode": "rpg",
            "colour_scheme": "dark",
        },
    )
    assert response.status_code == 201, response.text
    assert response.json()["profile"] == {"mode": "rpg", "colour_scheme": "dark"}
    assert client.get("/api/auth/me").json()["profile"] == {"mode": "rpg", "colour_scheme": "dark"}


def test_register_without_a_theme_uses_the_defaults(client):
    assert sign_up(client, verified=False)["profile"] == {
        "mode": "professional",
        "colour_scheme": "system",
    }


def test_session_cookie_is_http_only_and_same_site(client):
    response = client.post(
        "/api/auth/register",
        json={"email": "c@example.com", "password": "correct horse battery", "display_name": "C"},
    )
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=lax" in cookie


def test_mutations_require_the_csrf_token(client):
    sign_up(client)
    response = client.post("/api/exercises/starter.one/attempts", json={"files": WRONG})
    assert response.status_code == 403
    assert "CSRF" in response.json()["detail"]


def test_cross_origin_writes_are_refused(client):
    me = sign_up(client)
    response = client.post(
        "/api/exercises/starter.one/attempts",
        json={"files": WRONG},
        headers={"x-csrf-token": me["csrf_token"], "origin": "https://evil.example"},
    )
    assert response.status_code == 403


def test_full_journey_submit_grade_earn_and_unlock(client, factory, catalogue):
    me = sign_up(client)
    csrf = {"x-csrf-token": me["csrf_token"]}

    branches = client.get("/api/map").json()["branches"]
    assert [b["unlocked"] for b in branches] == [True, False]
    assert [b["kind"] for b in branches] == ["standard", "standard"]

    exercise = client.get("/api/exercises/starter.one").json()
    assert exercise["status"] == "available"
    assert set(exercise["files"]) == {"solution_mod.py"}
    assert (exercise["files_source"], exercise["carried_from"]) == ("starter", None)
    assert "solution" not in exercise and "tests" not in exercise

    queued = client.post(
        "/api/exercises/starter.one/attempts", json={"files": CORRECT}, headers=csrf
    )
    assert queued.status_code == 202
    assert queued.json()["status"] == "queued"

    run_worker_once(factory, catalogue)
    attempt = client.get(f"/api/attempts/{queued.json()['id']}").json()
    assert attempt["status"] == "passed"
    assert attempt["progression"]["xp_awarded"] == 50
    assert attempt["progression"]["unlocked"] == ["starter.two"]

    statuses = {
        e["id"]: e["status"] for e in client.get("/api/map").json()["branches"][0]["exercises"]
    }
    assert statuses == {"starter.one": "passed", "starter.two": "available"}

    # The draft survives: reopening the exercise returns the submitted code.
    assert client.get("/api/exercises/starter.one").json()["files"] == CORRECT


def test_hints_are_revealed_one_at_a_time(client, factory, catalogue):
    me = sign_up(client)
    csrf = {"x-csrf-token": me["csrf_token"]}
    client.post("/api/exercises/starter.one/attempts", json={"files": CORRECT}, headers=csrf)
    run_worker_once(factory, catalogue)

    assert client.post("/api/exercises/starter.two/hints", headers=csrf).json() == {
        "hints_revealed": ["h1"],
        "hints_total": 2,
    }
    client.post("/api/exercises/starter.two/hints", headers=csrf)
    exhausted = client.post("/api/exercises/starter.two/hints", headers=csrf)
    assert exhausted.status_code == 409


def test_learners_cannot_read_each_others_attempts(client):
    me = sign_up(client)
    attempt = client.post(
        "/api/exercises/starter.one/attempts",
        json={"files": WRONG},
        headers={"x-csrf-token": me["csrf_token"]},
    ).json()
    client.cookies.clear()
    sign_up(client, email="mallory@example.com")
    assert client.get(f"/api/attempts/{attempt['id']}").status_code == 404


def test_profile_changes_presentation_only(client):
    me = sign_up(client)
    updated = client.patch(
        "/api/auth/profile",
        json={"mode": "rpg", "colour_scheme": "dark"},
        headers={"x-csrf-token": me["csrf_token"]},
    ).json()
    assert updated["profile"] == {"mode": "rpg", "colour_scheme": "dark"}


def test_logout_ends_the_session(client):
    me = sign_up(client)
    assert (
        client.post("/api/auth/logout", headers={"x-csrf-token": me["csrf_token"]}).status_code
        == 204
    )
    assert client.get("/api/auth/me").status_code == 401


def test_rpg_flavour_is_public(client):
    assert client.get("/api/themes/rpg/flavour").json() == {
        "branches": {},
        "paths": {},
        "quests": {},
        "bosses": {},
    }
