"""HTTP contract for profile, talents, badges and reference solutions."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from lattice.api.app import create_app
from lattice.application.content_sync import sync_content
from lattice.domain.content import ContentError
from lattice.infrastructure.db.engine import transaction
from lattice.settings import Settings
from tests.integration.test_api import ORIGIN, sign_up
from tests.integration.test_learning_flow import CORRECT, run_worker_once
from tests.integration.test_progression_flow import catalogue, pass_everything  # noqa: F401


@pytest.fixture
def client(engine, factory, catalogue, tmp_path) -> Iterator[TestClient]:  # noqa: F811
    with transaction(factory) as session:
        sync_content(session, catalogue.graph)
    settings = Settings(
        content_dir=tmp_path, database_url=str(engine.url), allowed_origins="", log_level="WARNING"
    )
    with TestClient(create_app(settings, engine=engine), headers={"origin": ORIGIN}) as client:
        yield client


def complete_everything(client: TestClient, factory, catalogue, csrf) -> None:  # noqa: F811
    for exercise_id in ("starter.one", "starter.two", "retrieval.chunking"):
        queued = client.post(
            f"/api/exercises/{exercise_id}/attempts", json={"files": CORRECT}, headers=csrf
        )
        assert queued.status_code == 202, queued.text
        run_worker_once(factory, catalogue)


def csrf_of(me: dict) -> dict[str, str]:
    return {"x-csrf-token": me["csrf_token"]}


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", "/api/profile"),
        ("put", "/api/profile"),
        ("get", "/api/talents"),
        ("post", "/api/talents/respec"),
        ("post", "/api/talents/root/allocation"),
        ("delete", "/api/talents/root/allocation"),
        ("get", "/api/badges"),
        ("get", "/api/exercises/starter.one/reference-solution"),
    ],
)
def test_every_endpoint_needs_a_signed_in_learner(client, method, path):
    response = getattr(client, method)(path)
    assert response.status_code == 401
    assert response.headers["content-type"] == "application/problem+json"


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("put", "/api/profile"),
        ("post", "/api/talents/respec"),
        ("post", "/api/talents/root/allocation"),
        ("delete", "/api/talents/root/allocation"),
    ],
)
def test_mutations_need_the_csrf_token_and_a_same_origin_request(client, method, path):
    me = sign_up(client)
    assert getattr(client, method)(path).status_code == 403
    cross = getattr(client, method)(path, headers={**csrf_of(me), "origin": "https://evil.example"})
    assert cross.status_code == 403


def test_registration_accepts_a_time_zone(client):
    response = client.post(
        "/api/auth/register",
        json={
            "email": "tz@example.com",
            "password": "correct horse battery",
            "display_name": "T",
            "time_zone": "Asia/Tokyo",
        },
    )
    assert response.status_code == 201
    assert client.get("/api/profile").json()["time_zone"] == "Asia/Tokyo"

    client.cookies.clear()
    bad = client.post(
        "/api/auth/register",
        json={
            "email": "bad@example.com",
            "password": "correct horse battery",
            "display_name": "B",
            "time_zone": "Nowhere/Land",
        },
    )
    assert bad.status_code == 422 and bad.json()["code"] == "invalid-input"


def test_a_new_learner_is_a_generalist_in_utc(client):
    sign_up(client)
    profile = client.get("/api/profile").json()
    assert profile["path"] == "generalist" and profile["time_zone"] == "UTC"
    assert profile["titles"] == []
    paths = {p["id"]: p for p in profile["paths"]}
    assert paths["generalist"]["selectable"] is True
    assert paths["retrieval"]["selectable"] is False
    assert paths["retrieval"]["reason"] == "Complete Starter first."
    assert paths["retrieval"]["requires"] == [{"id": "starter", "title": "Starter"}]
    assert paths["generalist"]["requires"] == []
    assert "branch" not in paths["generalist"]["summary"]


def test_profile_update_validates_the_zone_and_gates_the_path(client):
    me = sign_up(client)
    csrf = csrf_of(me)

    bad = client.put("/api/profile", json={"time_zone": "Mars/Base"}, headers=csrf)
    assert bad.status_code == 422
    assert bad.headers["content-type"] == "application/problem+json"

    early = client.put("/api/profile", json={"path": "retrieval"}, headers=csrf)
    assert early.status_code == 403 and early.json()["code"] == "forbidden"

    unknown = client.put("/api/profile", json={"path": "wizard"}, headers=csrf)
    assert unknown.status_code == 422

    ok = client.put("/api/profile", json={"time_zone": "Europe/London"}, headers=csrf)
    assert ok.status_code == 200 and ok.json()["time_zone"] == "Europe/London"


def test_the_map_carries_the_streak(client, factory, catalogue):  # noqa: F811
    me = sign_up(client)
    assert client.get("/api/map").json()["streak"] == {"current": 0, "longest": 0}
    client.post("/api/exercises/starter.one/attempts", json={"files": CORRECT}, headers=csrf_of(me))
    run_worker_once(factory, catalogue)
    assert client.get("/api/map").json()["streak"] == {"current": 1, "longest": 1}


def test_a_graded_attempt_reports_badges_points_and_streak(client, factory, catalogue):  # noqa: F811
    me = sign_up(client)
    queued = client.post(
        "/api/exercises/starter.one/attempts", json={"files": CORRECT}, headers=csrf_of(me)
    ).json()
    assert queued["progression"] is None
    run_worker_once(factory, catalogue)

    progression = client.get(f"/api/attempts/{queued['id']}").json()["progression"]
    assert [b["id"] for b in progression["badges_awarded"]] == ["first-steps", "right-first-time"]
    assert progression["talent_points_gained"] == 0
    assert progression["streak"] == {"current": 1, "longest": 1}


def test_talent_tree_states_and_the_allocation_cycle(client, factory, catalogue):  # noqa: F811
    me = sign_up(client)
    csrf = csrf_of(me)

    tree = client.get("/api/talents").json()
    assert tree["path"] == "generalist"
    assert (tree["total_points"], tree["spent_points"], tree["available_points"]) == (0, 0, 0)
    assert [n["id"] for n in tree["nodes"]] == ["root", "kid"]  # the retrieval subtree is hidden
    root = tree["nodes"][0]
    assert root["state"] == "locked"
    assert {r["code"] for r in root["reasons"]} == {"level", "exercises", "no-points"}
    assert root["effects"] == [{"kind": "title", "value": "Prompt engineer"}]

    locked = client.post("/api/talents/root/allocation", headers=csrf)
    assert locked.status_code == 409 and locked.json()["code"] == "conflict"
    assert "Needs level 2" in locked.json()["detail"]
    assert client.post("/api/talents/ghost/allocation", headers=csrf).status_code == 404

    complete_everything(client, factory, catalogue, csrf)
    assert client.put("/api/profile", json={"path": "retrieval"}, headers=csrf).status_code == 200
    tree = client.get("/api/talents").json()
    assert tree["available_points"] == 3
    states = {n["id"]: n["state"] for n in tree["nodes"]}
    assert states == {"root": "available", "kid": "locked", "deep": "locked"}

    taken = client.post("/api/talents/root/allocation", headers=csrf).json()
    assert {n["id"]: n["state"] for n in taken["nodes"]} == {
        "root": "allocated",
        "kid": "available",
        "deep": "available",
    }
    assert taken["spent_points"] == 1 and taken["available_points"] == 2
    assert client.get("/api/profile").json()["titles"] == ["Prompt engineer"]

    client.post("/api/talents/kid/allocation", headers=csrf)
    assert client.delete("/api/talents/root/allocation", headers=csrf).status_code == 409
    assert client.delete("/api/talents/kid/allocation", headers=csrf).status_code == 200

    respec = client.post("/api/talents/respec", headers=csrf).json()
    assert respec["spent_points"] == 0 and respec["available_points"] == 3


def test_changing_path_reports_the_dropped_talents(client, factory, catalogue):  # noqa: F811
    me = sign_up(client)
    csrf = csrf_of(me)
    complete_everything(client, factory, catalogue, csrf)
    client.put("/api/profile", json={"path": "retrieval"}, headers=csrf)
    client.post("/api/talents/root/allocation", headers=csrf)
    client.post("/api/talents/deep/allocation", headers=csrf)

    switched = client.put("/api/profile", json={"path": "generalist"}, headers=csrf).json()
    assert switched["path"] == "generalist" and switched["dropped_talents"] == ["deep"]
    assert client.get("/api/talents").json()["spent_points"] == 1


def test_badges_list_earned_and_unearned_with_criteria(client, factory, catalogue):  # noqa: F811
    me = sign_up(client)
    before = {b["id"]: b for b in client.get("/api/badges").json()["badges"]}
    assert len(before) == 5 and not any(b["earned"] for b in before.values())
    assert before["foundations"]["criterion"] == "Pass every exercise in Starter."
    assert before["foundations"]["requirement"] == {
        "kind": "branch_complete",
        "n": None,
        "branch": {"id": "starter", "title": "Starter"},
    }
    assert before["first-steps"]["requirement"] == {
        "kind": "exercises_passed",
        "n": 1,
        "branch": None,
    }

    client.post("/api/exercises/starter.one/attempts", json={"files": CORRECT}, headers=csrf_of(me))
    run_worker_once(factory, catalogue)
    after = {b["id"]: b for b in client.get("/api/badges").json()["badges"]}
    assert after["first-steps"]["earned"] is True
    assert after["first-steps"]["awarded_at"] and after["first-steps"]["attempt_id"]
    assert after["foundations"]["earned"] is False and after["foundations"]["awarded_at"] is None


def test_reference_solution_is_forbidden_until_entitled(client, factory, catalogue):  # noqa: F811
    me = sign_up(client)
    csrf = csrf_of(me)
    complete_everything(client, factory, catalogue, csrf)

    denied = client.get("/api/exercises/starter.one/reference-solution")
    assert denied.status_code == 403
    assert denied.headers["content-type"] == "application/problem+json"
    assert denied.json()["code"] == "forbidden"
    assert "Take Kid" in denied.json()["detail"]
    assert denied.json()["detail"].startswith("This reference solution is locked.")
    assert denied.json()["talents"] == [{"id": "kid", "title": "Kid", "path": None}]

    client.post("/api/talents/root/allocation", headers=csrf)
    client.post("/api/talents/kid/allocation", headers=csrf)
    granted = client.get("/api/exercises/starter.one/reference-solution")
    assert granted.status_code == 200
    assert granted.json() == {
        "files": {"solution_mod.py": "def add(a, b):\n    return a + b\n"},
        "notes": "",
    }
    assert client.get("/api/exercises/retrieval.chunking/reference-solution").status_code == 403
    assert client.get("/api/exercises/nope.nope/reference-solution").status_code == 404


def test_reference_solution_requires_a_pass(client):
    sign_up(client)
    response = client.get("/api/exercises/starter.one/reference-solution")
    assert response.status_code == 403
    assert "Pass this exercise" in response.json()["detail"]


def test_the_api_refuses_to_start_on_invalid_progression_content(engine, catalogue, tmp_path):  # noqa: F811
    (tmp_path / "progression" / "talents.yaml").write_text(
        "nodes:\n  - id: a\n    title: A\n    summary: s\n    parents: [ghost]\n"
        "    effects: [{title: T}]\n"
    )
    settings = Settings(
        content_dir=tmp_path, database_url=str(engine.url), allowed_origins="", log_level="WARNING"
    )
    with (
        pytest.raises(ContentError, match="unknown parent 'ghost'"),
        TestClient(create_app(settings, engine=engine)),
    ):
        pass
