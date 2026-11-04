"""Adversarial checks on the paywall: a free learner, or nobody, gets nothing from a Pro exercise.

Every Pro asset carries the marker `PAID`, so one search of each response body finds a leak
whatever field it hides in.
"""

from __future__ import annotations

import io
import zipfile
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from lattice.api.app import create_app
from lattice.application.content_sync import sync_content
from lattice.infrastructure.content_loader import ContentCatalogue, load_catalogue
from lattice.infrastructure.db.engine import transaction
from lattice.infrastructure.db.models import LiveRun, TalentAllocation, User, XpEvent
from lattice.settings import Settings
from tests.content_factory import write_branch, write_exercise
from tests.integration.test_api import ORIGIN, go_pro, sign_up
from tests.integration.test_learning_flow import CORRECT, run_worker_once

PAID = "PAID-CONTENT-MARKER"

FLAVOUR = f"""
branches: {{}}
quests:
  retrieval.cap: The Last Archive
bosses:
  retrieval.cap:
    name: The Index Wyrm
    epithet: Hoarder of pages
    lore: {PAID} lore
    defeat: {PAID} defeat
"""


def _paid_assets(ex_dir: Path) -> None:
    (ex_dir / "brief.md").write_text(f"# Paid\n\n{PAID} brief\n")
    (ex_dir / "starter" / "solution_mod.py").write_text(f"# {PAID} starter\n")
    (ex_dir / "notes.md").write_text(f"{PAID} notes\n")
    (ex_dir / "python.md").write_text(f"### {PAID} python\n")
    (ex_dir / "live.py").write_text(f"print('{PAID} live')\n")


@pytest.fixture
def catalogue(tmp_path: Path) -> ContentCatalogue:
    """Starter: one (free). Retrieval: a (free), b (Pro, past an allowance of one, with hints,
    notes and a live.py), cap (capstone, with a boss). Every Pro asset carries PAID."""
    write_branch(tmp_path, "starter", order=0)
    write_branch(tmp_path, "retrieval", order=1, requires=["starter"])
    write_exercise(tmp_path, "starter", "one")
    write_exercise(tmp_path, "retrieval", "a", xp=50)
    b = write_exercise(
        tmp_path,
        "retrieval",
        "b",
        xp=60,
        hints=[f"{PAID} hint"],
        checks=[{"id": "adds", "title": f"{PAID} check", "test": "test_add.py::test_adds"}],
    )
    _paid_assets(b)
    cap = write_exercise(
        tmp_path,
        "retrieval",
        "cap",
        tier="capstone",
        xp=300,
        prerequisites=["retrieval.a", "retrieval.b"],
    )
    _paid_assets(cap)
    (tmp_path / "themes" / "rpg").mkdir(parents=True)
    (tmp_path / "themes" / "rpg" / "flavour.yaml").write_text(FLAVOUR)
    progression_dir = tmp_path / "progression"
    progression_dir.mkdir()
    (progression_dir / "classes.yaml").write_text("paths: []\n")
    (progression_dir / "talents.yaml").write_text(
        "nodes:\n  - {id: archivist, title: Archivist, summary: s,"
        " effects: [{reference_solutions: retrieval}]}\n"
    )
    (progression_dir / "badges.yaml").write_text("badges: []\n")
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


def csrf(me: dict) -> dict[str, str]:
    return {"x-csrf-token": me["csrf_token"]}


def no_paid(response) -> None:
    assert PAID not in response.text, f"{response.request.url}: {response.text[:400]}"


def set_plan(factory, plan: str) -> None:
    with transaction(factory) as session:
        session.scalars(select(User)).one().plan = plan


def test_a_free_learner_reads_nothing_of_a_pro_exercise_but_its_title(client):
    sign_up(client)
    for exercise_id in ("retrieval.b", "retrieval.cap"):
        detail = client.get(f"/api/exercises/{exercise_id}")
        assert detail.status_code == 200
        no_paid(detail)
        body = detail.json()
        assert (body["pro"], body["entitled"]) == (True, False)
        assert (body["brief"], body["files"], body["editable"], body["checks"]) == ("", {}, [], [])
        assert (body["hints_total"], body["has_live_example"]) == (0, False)


def test_python_notes_never_reach_a_learner_who_is_not_entitled(client, factory):
    sign_up(client)
    for exercise_id in ("retrieval.b", "retrieval.cap"):
        detail = client.get(f"/api/exercises/{exercise_id}")
        no_paid(detail)
        assert detail.json()["python_notes"] == ""
        assert client.get(f"/api/exercises/{exercise_id}/download").status_code == 403
    no_paid(client.get("/api/map"))
    no_paid(client.get("/api/catalogue"))

    set_plan(factory, "pro")
    assert PAID in client.get("/api/exercises/retrieval.b").json()["python_notes"]
    with zipfile.ZipFile(
        io.BytesIO(client.get("/api/exercises/retrieval.b/download").content)
    ) as z:
        assert PAID in z.read("retrieval.b/python.md").decode()

    set_plan(factory, "free")  # lost at once, like the brief
    no_paid(client.get("/api/exercises/retrieval.b"))


def test_a_missing_python_file_means_no_notes_on_any_plan(client, factory):
    sign_up(client)
    assert client.get("/api/exercises/retrieval.a").json()["python_notes"] == ""
    set_plan(factory, "pro")
    assert client.get("/api/exercises/retrieval.a").json()["python_notes"] == ""
    with zipfile.ZipFile(
        io.BytesIO(client.get("/api/exercises/retrieval.a/download").content)
    ) as z:
        assert "retrieval.a/python.md" not in z.namelist()


def test_a_free_learner_cannot_save_reset_or_download_a_pro_exercise(client):
    me = sign_up(client)
    url = "/api/exercises/retrieval.b"
    responses = [
        client.put(f"{url}/draft", json={"files": CORRECT}, headers=csrf(me)),
        client.delete(f"{url}/draft", headers=csrf(me)),
        client.get(f"{url}/download"),
        client.post(f"{url}/hints", headers=csrf(me)),
        client.post(f"{url}/attempts", json={"files": CORRECT}, headers=csrf(me)),
        client.post(f"{url}/live-runs", json={"files": CORRECT}, headers=csrf(me)),
        client.put(f"{url}/draft", json={"files": {"other.py": "x"}}, headers=csrf(me)),
    ]
    for response in responses:
        no_paid(response)
        assert response.status_code in (403, 503), response.text
        if response.status_code == 403:
            assert response.json()["code"] == "plan-required"
            assert "brief" not in response.json()["detail"]
    assert client.get("/api/exercises/nothing.here/draft").status_code in (404, 405)
    unknown = client.put(
        "/api/exercises/nothing.here/draft", json={"files": CORRECT}, headers=csrf(me)
    )
    assert unknown.status_code == 404


def test_a_learner_back_on_free_loses_the_pro_brief_and_reference_solution_at_once(
    client, factory, catalogue
):
    """Entitlement is read from the account on every request: no session or cache keeps Pro."""
    me = sign_up(client)
    go_pro(factory)
    queued = client.post(
        "/api/exercises/retrieval.b/attempts", json={"files": CORRECT}, headers=csrf(me)
    )
    assert queued.status_code == 202, queued.text
    run_worker_once(factory, catalogue, free_per_branch=1)
    with transaction(factory) as session:
        user_id = session.scalars(select(User.id)).one()
        session.add(TalentAllocation(user_id=user_id, node_id="archivist"))
        session.add(XpEvent(user_id=user_id, reason="test", amount=1000))  # a talent point
    assert PAID in client.get("/api/exercises/retrieval.b").json()["brief"]
    granted = client.get("/api/exercises/retrieval.b/reference-solution")
    assert granted.status_code == 200, granted.text

    # Billing sets the plan to free on canceled, unpaid or paused (`plan_for`, unit-tested).
    set_plan(factory, "free")
    detail = client.get("/api/exercises/retrieval.b")
    no_paid(detail)
    assert detail.json()["status"] == "passed"  # progress is never taken away
    solution = client.get("/api/exercises/retrieval.b/reference-solution")
    no_paid(solution)
    assert (solution.status_code, solution.json()["code"]) == (403, "plan-required")


def test_nobody_signed_in_reaches_pro_content(client):
    for url in (
        "/api/catalogue",
        "/api/themes/rpg/flavour",
        "/api/config",
        "/openapi.json",
        "/docs",
        "/kit/live-mode.md",
        "/kit/toolkit-reference.md",
        "/kit/latest",
        "/api/exercises/retrieval.b",
        "/api/exercises/retrieval.b/download",
        "/api/exercises/retrieval.b/reference-solution",
        "/api/releases",
        "/api/map",
        "/api/account/export",
    ):
        no_paid(client.get(url))
    catalogue = client.get("/api/catalogue").json()
    exercises = [e for b in catalogue["branches"] for e in b["exercises"]]
    (cap,) = [e for e in exercises if e["id"] == "retrieval.cap"]
    assert set(cap) == {
        "id", "title", "tier", "xp", "skills", "prerequisites", "status", "pro", "entitled"
    }  # fmt: skip


def test_the_rpg_flavour_keeps_a_pro_bosss_lore_for_paid_learners(client, factory):
    anonymous = client.get("/api/themes/rpg/flavour").json()
    assert anonymous["bosses"]["retrieval.cap"]["name"] == "The Index Wyrm"
    assert anonymous["quests"]["retrieval.cap"] == "The Last Archive"
    sign_up(client)
    no_paid(client.get("/api/themes/rpg/flavour"))
    go_pro(factory)
    assert client.get("/api/themes/rpg/flavour").json()["bosses"]["retrieval.cap"]["lore"] == (
        f"{PAID} lore"
    )


def test_a_learner_cannot_read_anothers_attempts_live_runs_or_export(client, factory, catalogue):
    ada = sign_up(client)
    queued = client.post(
        "/api/exercises/starter.one/attempts", json={"files": CORRECT}, headers=csrf(ada)
    )
    attempt_id = queued.json()["id"]
    with transaction(factory) as session:
        ada_id = session.scalars(select(User.id)).one()
        run = LiveRun(user_id=ada_id, exercise_id="starter.one", files=CORRECT, status="queued")
        session.add(run)
        session.flush()
        run_id = run.id
    client.put("/api/exercises/starter.one/draft", json={"files": CORRECT}, headers=csrf(ada))

    client.cookies.clear()
    sign_up(client, "bob@example.com")
    assert client.get(f"/api/attempts/{attempt_id}").status_code == 404
    assert client.get(f"/api/live-runs/{run_id}").status_code == 404
    assert client.get("/api/exercises/starter.one").json()["files"] != CORRECT
    exported = client.get("/api/account/export")
    assert exported.status_code == 200
    assert str(attempt_id) not in exported.text and "return a + b" not in exported.text
