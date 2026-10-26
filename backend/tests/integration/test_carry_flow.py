"""Carrying a learner's files from one exercise to the next, as a project's milestones do."""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from lattice.application import accounts, learning
from lattice.application.content_sync import sync_content
from lattice.infrastructure.content_loader import ContentCatalogue, load_catalogue
from lattice.infrastructure.db.engine import transaction
from tests.content_factory import write_branch, write_exercise
from tests.integration.test_api import client, go_pro, sign_up  # noqa: F401
from tests.integration.test_learning_flow import CORRECT, WRONG, run_worker_once, submit

STARTER_MOD = "def add(a, b):\n    raise NotImplementedError\n"
STARTER_EXTRA = "# extend me\n"


@pytest.fixture
def catalogue(tmp_path: Path) -> ContentCatalogue:
    """Starter: one. Project (requires starter): ingest -> serve, which carries from ingest and
    adds `extra.py` to what the learner edits."""
    write_branch(tmp_path, "starter", order=0)
    write_branch(tmp_path, "project", order=1, requires=["starter"], kind="project")
    write_exercise(tmp_path, "starter", "one")
    write_exercise(tmp_path, "project", "ingest")
    serve = write_exercise(
        tmp_path,
        "project",
        "serve",
        prerequisites=["project.ingest"],
        carry_from="project.ingest",
        editable=["solution_mod.py", "extra.py"],
    )
    (serve / "starter" / "extra.py").write_text(STARTER_EXTRA)
    (serve / "solution" / "extra.py").write_text(STARTER_EXTRA)
    return load_catalogue(tmp_path)


@pytest.fixture
def learner(factory, catalogue) -> uuid.UUID:
    """A Pro learner who has finished the starter branch, so the project is open."""
    with transaction(factory) as session:
        sync_content(session, catalogue.graph)
        user = accounts.register(
            session, email="ada@example.com", password="correct horse battery", display_name="Ada"
        )
        user.plan = "pro"  # guided projects are Pro
    submit(factory, catalogue, user.id, "starter.one", CORRECT)
    run_worker_once(factory, catalogue)
    return user.id


def view(factory, catalogue, user_id) -> learning.ExerciseView:
    with factory() as session:
        return learning.exercise_view(
            session, catalogue, user_id, "project.serve", free_per_branch=3
        )


def pass_ingest(factory, catalogue, user_id, files) -> None:
    submit(factory, catalogue, user_id, "project.ingest", files)
    run_worker_once(factory, catalogue)


def test_without_a_passing_attempt_the_exercise_opens_on_its_starter(factory, catalogue, learner):
    submit(factory, catalogue, learner, "project.ingest", WRONG)
    run_worker_once(factory, catalogue)

    opened = view(factory, catalogue, learner)
    assert opened.files == {"solution_mod.py": STARTER_MOD, "extra.py": STARTER_EXTRA}
    assert (opened.files_source, opened.carried_from) == ("starter", None)


def test_the_latest_passing_files_are_carried_and_new_paths_fall_back_to_the_starter(
    factory, catalogue, learner
):
    first = {"solution_mod.py": "def add(a, b):\n    return a + b  # first\n"}
    second = {"solution_mod.py": "def add(a, b):\n    return a + b  # second\n"}
    pass_ingest(factory, catalogue, learner, first)
    pass_ingest(factory, catalogue, learner, second)
    submit(factory, catalogue, learner, "project.ingest", WRONG)  # a later failure is ignored
    run_worker_once(factory, catalogue)

    opened = view(factory, catalogue, learner)
    assert opened.files == {**second, "extra.py": STARTER_EXTRA}
    assert (opened.files_source, opened.carried_from) == ("carried", "project.ingest")


def test_a_draft_wins_over_carried_files(factory, catalogue, learner):
    pass_ingest(factory, catalogue, learner, CORRECT)
    with transaction(factory) as session:
        learning.save_draft(session, catalogue, learner, "project.serve", {"extra.py": "# mine\n"})

    opened = view(factory, catalogue, learner)
    assert opened.files == {"solution_mod.py": STARTER_MOD, "extra.py": "# mine\n"}
    assert (opened.files_source, opened.carried_from) == ("draft", None)


def test_a_reset_returns_to_the_starter_and_carried_files_do_not_come_back(
    factory, catalogue, learner
):
    pass_ingest(factory, catalogue, learner, CORRECT)
    with transaction(factory) as session:
        learning.save_draft(session, catalogue, learner, "project.serve", {"extra.py": "# mine\n"})
    with transaction(factory) as session:
        learning.reset_to_starter(session, catalogue, learner, "project.serve")

    opened = view(factory, catalogue, learner)
    assert opened.files == {"solution_mod.py": STARTER_MOD, "extra.py": STARTER_EXTRA}
    assert opened.files_source == "starter"

    with transaction(factory) as session:  # a reset with no draft yet also sticks
        learning.reset_to_starter(session, catalogue, learner, "project.ingest")
    with factory() as session:
        ingest = learning.exercise_view(
            session, catalogue, learner, "project.ingest", free_per_branch=3
        )
    assert ingest.files_source == "starter"


def test_the_api_reports_where_files_came_from_and_resets_under_csrf(client, factory, catalogue):  # noqa: F811
    csrf = {"x-csrf-token": sign_up(client)["csrf_token"]}
    go_pro(factory)
    for exercise_id in ("starter.one", "project.ingest"):
        queued = client.post(
            f"/api/exercises/{exercise_id}/attempts", json={"files": CORRECT}, headers=csrf
        )
        assert queued.status_code == 202, queued.text
        run_worker_once(factory, catalogue)

    detail = client.get("/api/exercises/project.serve").json()
    assert detail["files"] == {**CORRECT, "extra.py": STARTER_EXTRA}
    assert (detail["files_source"], detail["carried_from"]) == ("carried", "project.ingest")
    project = client.get("/api/map").json()["branches"][1]
    assert (project["id"], project["kind"]) == ("project", "project")

    assert client.delete("/api/exercises/project.serve/draft").status_code == 403
    cross = client.delete(
        "/api/exercises/project.serve/draft", headers={**csrf, "origin": "https://evil.example"}
    )
    assert cross.status_code == 403

    reset = client.delete("/api/exercises/project.serve/draft", headers=csrf)
    assert reset.status_code == 200
    assert reset.json()["files"] == {"solution_mod.py": STARTER_MOD, "extra.py": STARTER_EXTRA}
    assert (reset.json()["files_source"], reset.json()["carried_from"]) == ("starter", None)
    assert client.get("/api/exercises/project.serve").json()["files_source"] == "starter"
    assert client.delete("/api/exercises/project.nope/draft", headers=csrf).status_code == 404
