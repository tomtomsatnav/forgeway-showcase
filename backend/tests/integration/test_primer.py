"""A primer over HTTP: free to everyone, and it asks for and awards nothing a track does."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from lattice.api.app import create_app
from lattice.application.content_sync import sync_content
from lattice.infrastructure.content_loader import ContentCatalogue, load_catalogue
from lattice.infrastructure.db.engine import transaction
from lattice.settings import Settings
from tests.content_factory import write_branch, write_exercise
from tests.integration.test_api import ORIGIN, sign_up
from tests.integration.test_learning_flow import CORRECT, run_worker_once


@pytest.fixture
def catalogue(tmp_path: Path) -> ContentCatalogue:
    """A one-exercise foundation, a track past a free allowance of one, a primer of three."""
    write_branch(tmp_path, "starter", order=0)
    write_branch(tmp_path, "retrieval", order=1, requires=["starter"])
    write_branch(tmp_path, "primer", order=2, kind="primer")
    write_exercise(tmp_path, "starter", "one")
    write_exercise(tmp_path, "retrieval", "a", xp=50)
    write_exercise(tmp_path, "retrieval", "b", xp=60)
    for index, slug in enumerate(("p", "q", "r")):
        write_exercise(tmp_path, "primer", slug, xp=50 + index)
    return load_catalogue(tmp_path)


@pytest.fixture
def client(engine, factory, catalogue, tmp_path) -> Iterator[TestClient]:
    with transaction(factory) as session:
        sync_content(session, catalogue.graph)
    settings = Settings(
        content_dir=tmp_path,
        database_url=engine.url.render_as_string(hide_password=False),
        allowed_origins="",
        log_level="WARNING",
        free_exercises_per_branch=1,
    )
    with TestClient(create_app(settings, engine=engine), headers={"origin": ORIGIN}) as client:
        yield client


def branch(client, branch_id: str) -> dict:
    branches = client.get("/api/map").json()["branches"]
    return next(b for b in branches if b["id"] == branch_id)


def test_a_primer_is_open_to_a_free_learner_past_the_free_count(client):
    sign_up(client)
    primer = branch(client, "primer")
    assert primer["kind"] == "primer"
    assert (primer["unlocked"], primer["pro"]) == (True, False)
    assert [(e["pro"], e["entitled"], e["status"]) for e in primer["exercises"]] == [
        (False, True, "available")
    ] * 3
    detail = client.get("/api/exercises/primer.r").json()
    assert (detail["pro"], detail["entitled"]) == (False, True)
    assert detail["brief"]


def test_a_primer_leaves_the_free_exercises_of_other_tracks_alone(client):
    sign_up(client)
    pro = {e["id"]: e["pro"] for e in branch(client, "retrieval")["exercises"]}
    assert pro == {"retrieval.a": False, "retrieval.b": True}


def test_passing_a_primer_exercise_opens_its_reference_solution_and_issues_no_certificate(
    client, factory, catalogue
):
    me = sign_up(client)
    headers = {"x-csrf-token": me["csrf_token"]}
    assert client.get("/api/exercises/primer.p/reference-solution").status_code == 403

    for slug in ("p", "q", "r"):
        exercise_id = f"primer.{slug}"
        submitted = client.post(
            f"/api/exercises/{exercise_id}/attempts", json={"files": CORRECT}, headers=headers
        )
        assert submitted.status_code == 202, submitted.text
        run_worker_once(factory, catalogue)

    assert branch(client, "primer")["passed_count"] == 3
    assert client.get("/api/exercises/primer.p/reference-solution").status_code == 200
    assert client.get("/api/certificates").json()["certificates"] == []
    # And nothing in the rest of the course moved.
    assert branch(client, "retrieval")["unlocked"] is False
