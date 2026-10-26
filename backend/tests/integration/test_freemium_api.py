"""Plans, entitlements, the Pro waitlist and release notes, through the API and the CLI."""

from __future__ import annotations

import csv
import io
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from typer.testing import CliRunner

from lattice.api.app import create_app
from lattice.application.content_sync import sync_content
from lattice.cli import app as cli
from lattice.infrastructure.content_loader import ContentCatalogue, load_catalogue
from lattice.infrastructure.db.engine import transaction
from lattice.infrastructure.db.models import Attempt, Certificate, ProWaitlistEntry, User
from lattice.settings import Settings
from lattice.worker.main import Worker
from tests.content_factory import write_branch, write_exercise
from tests.fakes import ScriptedRunner
from tests.integration.test_api import ORIGIN, go_pro, sign_up
from tests.integration.test_learning_flow import CORRECT, run_worker_once

RELEASE = """---
version: 2026.10.0
date: 2026-10-26
title: The first release
summary: Everything so far.
added: [retrieval.cap]
updated: [starter.one]
---
Body in **Markdown**.
"""


@pytest.fixture
def catalogue(tmp_path: Path) -> ContentCatalogue:
    """Starter: one. Retrieval: a (free), b (Pro: past the allowance of one), cap (capstone).
    Graphs, which requires Retrieval: x (free). Project: m1. One release note, and a Graphs
    specialisation path."""
    write_branch(tmp_path, "starter", order=0)
    write_branch(tmp_path, "retrieval", order=1, requires=["starter"])
    write_branch(tmp_path, "project", order=2, requires=["starter"], kind="project")
    write_branch(tmp_path, "graphs", order=3, requires=["retrieval"])
    write_exercise(tmp_path, "starter", "one")
    write_exercise(tmp_path, "retrieval", "a", xp=50)
    write_exercise(
        tmp_path, "retrieval", "b", xp=60, prerequisites=["retrieval.a"], hints=["h1", "h2"]
    )
    write_exercise(
        tmp_path,
        "retrieval",
        "cap",
        tier="capstone",
        xp=300,
        prerequisites=["retrieval.a", "retrieval.b"],
    )
    write_exercise(tmp_path, "project", "m1")
    write_exercise(tmp_path, "graphs", "x")
    (tmp_path / "releases").mkdir()
    (tmp_path / "releases" / "2026.10.0.md").write_text(RELEASE)
    progression_dir = tmp_path / "progression"
    progression_dir.mkdir()
    (progression_dir / "classes.yaml").write_text(
        "paths:\n  - {id: graphs, title: Graphs, summary: s, home_branch: graphs}\n"
    )
    (progression_dir / "talents.yaml").write_text("nodes: []\n")
    (progression_dir / "badges.yaml").write_text("badges: []\n")
    return load_catalogue(tmp_path)


@pytest.fixture
def settings(engine, tmp_path) -> Settings:
    """A free allowance of one, not the default three, so a path that ignores the setting and
    falls back to the default is caught."""
    return Settings(
        content_dir=tmp_path,
        database_url=engine.url.render_as_string(hide_password=False),
        allowed_origins="",
        log_level="WARNING",
        free_exercises_per_branch=1,
    )


@pytest.fixture
def client(engine, factory, catalogue, settings) -> Iterator[TestClient]:
    with transaction(factory) as session:
        sync_content(session, catalogue.graph)
    with TestClient(create_app(settings, engine=engine), headers={"origin": ORIGIN}) as client:
        yield client


def csrf(me: dict) -> dict[str, str]:
    return {"x-csrf-token": me["csrf_token"]}


def attempt(client: TestClient, me: dict, exercise_id: str):
    return client.post(
        f"/api/exercises/{exercise_id}/attempts", json={"files": CORRECT}, headers=csrf(me)
    )


def pass_(client: TestClient, factory, catalogue, me: dict, exercise_id: str) -> None:
    queued = attempt(client, me, exercise_id)
    assert queued.status_code == 202, queued.text
    run_worker_once(factory, catalogue, free_per_branch=1)


def hint(client: TestClient, me: dict, exercise_id: str):
    return client.post(f"/api/exercises/{exercise_id}/hints", headers=csrf(me))


def test_a_new_account_is_free_and_existing_rows_default_to_free(client, factory):
    me = sign_up(client)
    assert me["plan"] == "free"
    with factory() as session:
        assert session.scalars(select(User.plan)).all() == ["free"]


def test_the_map_marks_pro_content_and_what_the_learner_is_entitled_to(client, factory):
    sign_up(client)
    branches = {b["id"]: b for b in client.get("/api/map").json()["branches"]}
    marks = {e["id"]: (e["pro"], e["entitled"]) for b in branches.values() for e in b["exercises"]}
    assert marks == {
        "starter.one": (False, True),
        "retrieval.a": (False, True),
        "retrieval.b": (True, False),
        "retrieval.cap": (True, False),
        "project.m1": (True, False),
        "graphs.x": (False, True),
    }
    assert {i: b["pro"] for i, b in branches.items()} == {
        "starter": False,
        "retrieval": False,
        "project": True,
        "graphs": False,
    }

    go_pro(factory)
    entitled = {
        e["id"]: e["entitled"]
        for b in client.get("/api/map").json()["branches"]
        for e in b["exercises"]
    }
    assert all(entitled.values())


def test_a_free_learner_reads_a_pro_brief_but_cannot_attempt_it(client, factory, catalogue):
    me = sign_up(client)
    pass_(client, factory, catalogue, me, "starter.one")

    detail = client.get("/api/exercises/retrieval.cap").json()
    assert (detail["pro"], detail["entitled"]) == (True, False)
    assert detail["brief"].startswith("# cap")

    for exercise_id in ("retrieval.cap", "retrieval.b", "project.m1"):
        refused = attempt(client, me, exercise_id)
        assert refused.status_code == 403
        assert refused.headers["content-type"] == "application/problem+json"
        body = refused.json()
        assert body["code"] == "plan-required"
        assert "Forgeway Pro" in body["detail"]
    assert attempt(client, me, "retrieval.a").status_code == 202


def test_a_free_learner_cannot_reveal_a_pro_exercises_hints(client, factory, catalogue):
    me = sign_up(client)
    for exercise_id in ("starter.one", "retrieval.a"):
        pass_(client, factory, catalogue, me, exercise_id)
    assert client.get("/api/exercises/retrieval.b").json()["status"] == "available"

    refused = hint(client, me, "retrieval.b")
    assert refused.status_code == 403
    assert refused.headers["content-type"] == "application/problem+json"
    assert refused.json()["code"] == "plan-required"
    assert client.get("/api/exercises/retrieval.b").json()["hints_revealed"] == []

    go_pro(factory)
    revealed = hint(client, me, "retrieval.b")
    assert revealed.status_code == 200, revealed.text
    assert revealed.json()["hints_revealed"] == ["h1"]


def test_a_non_default_free_allowance_is_honoured_everywhere(client, factory, catalogue, settings):
    """With an allowance of one, retrieval.b is Pro. Under the default of three it would be
    free, so each path below would answer differently if it fell back to the default."""
    me = sign_up(client)
    pass_(client, factory, catalogue, me, "starter.one")

    # Grading, through the worker itself: passing retrieval.a opens Graphs, because on the
    # free plan Pro exercises (b and the capstone) count as done.
    assert attempt(client, me, "retrieval.a").status_code == 202
    assert Worker(settings, catalogue, ScriptedRunner()).run_once()
    with factory() as session:
        row = session.scalars(select(Attempt).where(Attempt.exercise_id == "retrieval.a")).one()
    assert row.status == "passed"
    assert "graphs.x" in row.report["progression"]["unlocked"]

    # The exercise, attempts and hints.
    detail = client.get("/api/exercises/retrieval.b").json()
    assert (detail["pro"], detail["entitled"]) == (True, False)
    assert attempt(client, me, "retrieval.b").json()["code"] == "plan-required"
    assert hint(client, me, "retrieval.b").json()["code"] == "plan-required"
    # Path choice: Graphs' home branch is open, so its path can be chosen.
    paths = {p["id"]: p["selectable"] for p in client.get("/api/profile").json()["paths"]}
    assert paths["graphs"] is True
    chosen = client.put("/api/profile", json={"path": "graphs"}, headers=csrf(me))
    assert chosen.status_code == 200, chosen.text
    assert chosen.json()["path"] == "graphs"


def test_locked_by_plan_is_distinct_from_locked_by_prerequisites(client, factory, catalogue):
    me = sign_up(client)
    # Before the foundations are done the free exercise is locked by prerequisites only.
    locked = attempt(client, me, "retrieval.a")
    assert (locked.status_code, locked.json()["code"]) == (403, "forbidden")
    detail = client.get("/api/exercises/retrieval.a").json()
    assert (detail["status"], detail["entitled"]) == ("locked", True)

    go_pro(factory)
    # On Pro nothing is locked by prerequisites: the capstone is open with nothing passed.
    assert client.get("/api/exercises/retrieval.cap").json()["status"] == "available"
    assert attempt(client, me, "retrieval.cap").status_code == 202


def test_a_free_learner_unlocks_a_branch_once_the_free_exercises_it_requires_are_passed(
    client, factory, catalogue
):
    """Graphs requires Retrieval, whose capstone is Pro: on the free plan it opens once
    Retrieval's free exercises are passed (ADR 0011), not never."""
    me = sign_up(client)
    pass_(client, factory, catalogue, me, "starter.one")
    assert attempt(client, me, "graphs.x").json()["code"] == "forbidden"

    pass_(client, factory, catalogue, me, "retrieval.a")
    branches = {b["id"]: b for b in client.get("/api/map").json()["branches"]}
    assert branches["graphs"]["unlocked"] is True
    statuses = {e["id"]: e["status"] for b in branches.values() for e in b["exercises"]}
    assert statuses["graphs.x"] == "available"
    assert statuses["retrieval.b"] == "available"  # open by prerequisites, still Pro by plan
    assert statuses["retrieval.cap"] == "locked"  # its own prerequisite, b, is not passed
    assert client.get("/api/exercises/graphs.x").json()["status"] == "available"
    pass_(client, factory, catalogue, me, "graphs.x")

    # On Pro everything is open, and what was passed stays passed.
    go_pro(factory)
    branches = {b["id"]: b for b in client.get("/api/map").json()["branches"]}
    assert branches["graphs"]["unlocked"] is True
    statuses = {e["id"]: e["status"] for b in branches.values() for e in b["exercises"]}
    assert statuses["graphs.x"] == "passed"
    assert statuses["retrieval.cap"] == "available"


def test_a_pro_learner_can_attempt_capstones_and_projects(client, factory, catalogue):
    me = sign_up(client)
    go_pro(factory)
    for exercise_id in ("starter.one", "retrieval.a", "retrieval.b", "retrieval.cap"):
        pass_(client, factory, catalogue, me, exercise_id)
    statuses = {
        e["id"]: e["status"]
        for b in client.get("/api/map").json()["branches"]
        for e in b["exercises"]
    }
    assert statuses["retrieval.cap"] == "passed"
    assert attempt(client, me, "project.m1").status_code == 202


def test_progress_is_kept_when_a_learner_goes_back_to_free(client, factory, catalogue):
    me = sign_up(client)
    go_pro(factory)
    for exercise_id in ("starter.one", "retrieval.a", "retrieval.b"):
        pass_(client, factory, catalogue, me, exercise_id)
    with transaction(factory) as session:
        session.scalars(select(User)).one().plan = "free"
    exercises = {
        e["id"]: e for b in client.get("/api/map").json()["branches"] for e in b["exercises"]
    }
    assert exercises["retrieval.b"]["status"] == "passed"
    assert exercises["retrieval.b"]["entitled"] is False
    assert attempt(client, me, "retrieval.b").json()["code"] == "plan-required"


def test_publishing_a_certificate_needs_pro_but_unpublishing_and_renaming_do_not(
    client, factory, catalogue
):
    me = sign_up(client)
    pass_(client, factory, catalogue, me, "starter.one")
    (certificate,) = client.get("/api/certificates").json()["certificates"]
    url = f"/api/certificates/{certificate['id']}"

    refused = client.patch(url, json={"is_public": True}, headers=csrf(me))
    assert (refused.status_code, refused.json()["code"]) == (403, "plan-required")
    renamed = client.patch(url, json={"recipient_name": "Ada L."}, headers=csrf(me))
    assert renamed.status_code == 200

    go_pro(factory)
    assert client.patch(url, json={"is_public": True}, headers=csrf(me)).json()["is_public"]
    with transaction(factory) as session:
        session.scalars(select(User)).one().plan = "free"
    # A certificate made public stays public, and can still be taken down.
    with factory() as session:
        assert session.scalars(select(Certificate.is_public)).one() is True
    assert client.patch(url, json={"is_public": False}, headers=csrf(me)).status_code == 200


def test_joining_the_waitlist_is_idempotent_with_one_row_per_learner(client, factory):
    me = sign_up(client)
    assert client.get("/api/pro/waitlist").json() == {
        "joined": False,
        "plan_interest": None,
        "joined_at": None,
    }
    first = client.post("/api/pro/waitlist", json={}, headers=csrf(me))
    assert first.status_code == 200
    assert (first.json()["joined"], first.json()["plan_interest"]) == (True, "pro")
    again = client.post("/api/pro/waitlist", json={"plan": "team"}, headers=csrf(me))
    assert again.json()["joined_at"] == first.json()["joined_at"]
    assert again.json()["plan_interest"] == "team"
    assert client.get("/api/pro/waitlist").json() == again.json()
    with factory() as session:
        (row,) = session.scalars(select(ProWaitlistEntry)).all()
        assert (row.email, row.plan_interest) == ("ada@example.com", "team")


def test_the_waitlist_needs_a_session_and_a_csrf_token(client):
    assert client.get("/api/pro/waitlist").status_code == 401
    assert client.post("/api/pro/waitlist", json={}).status_code == 401
    me = sign_up(client)
    assert client.post("/api/pro/waitlist", json={}).status_code == 403
    bad = client.post("/api/pro/waitlist", json={"plan": "gold"}, headers=csrf(me))
    assert bad.status_code == 422


def test_the_releases_are_listed_with_their_exercises_and_an_unread_marker(client):
    me = sign_up(client)
    body = client.get("/api/releases").json()
    assert (body["unread"], body["last_seen"]) == (True, None)
    (release,) = body["releases"]
    assert release["version"] == "2026.10.0"
    assert release["date"] == "2026-10-26"
    assert release["added"] == [{"id": "retrieval.cap", "title": "Cap", "branch": "retrieval"}]
    assert release["updated"] == [{"id": "starter.one", "title": "One", "branch": "starter"}]
    assert release["fixed"] == []
    assert release["body"] == "Body in **Markdown**.\n"

    assert client.post("/api/releases/seen").status_code == 403  # CSRF
    seen = client.post("/api/releases/seen", headers=csrf(me)).json()
    assert (seen["unread"], seen["last_seen"]) == (False, "2026.10.0")
    assert client.post("/api/releases/seen", headers=csrf(me)).json() == seen
    assert client.get("/api/releases").json()["unread"] is False


def test_the_releases_need_a_session(client):
    assert client.get("/api/releases").status_code == 401


def test_the_owner_sets_a_plan_and_exports_the_waitlist_from_the_cli(client, factory):
    me = sign_up(client)
    client.post("/api/pro/waitlist", json={}, headers=csrf(me))
    runner = CliRunner()

    done = runner.invoke(cli, ["accounts", "set-plan", "ADA@example.com", "pro"])
    assert done.exit_code == 0, done.output
    assert client.get("/api/auth/me").json()["plan"] == "pro"
    assert runner.invoke(cli, ["accounts", "set-plan", "nobody@example.com", "pro"]).exit_code == 1
    assert runner.invoke(cli, ["accounts", "set-plan", "ada@example.com", "gold"]).exit_code != 0

    exported = runner.invoke(cli, ["waitlist", "export"])
    assert exported.exit_code == 0, exported.output
    rows = list(csv.reader(io.StringIO(exported.output)))
    assert rows[0] == ["email", "plan_interest", "joined_at"]
    assert [r[:2] for r in rows[1:]] == [["ada@example.com", "pro"]]
