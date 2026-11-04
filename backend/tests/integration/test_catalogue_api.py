"""The public catalogue: every branch as a brand-new free learner sees it, with no session."""

from __future__ import annotations

from tests.integration.test_api import sign_up
from tests.integration.test_freemium_api import (  # noqa: F401 (pytest fixtures)
    catalogue,
    client,
    csrf,
    pass_,
    settings,
)


def test_it_is_public_and_cacheable(client):  # noqa: F811
    # The fixture's client has never signed in.
    response = client.get("/api/catalogue")
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "public, max-age=300"


def test_it_is_what_a_new_free_learner_sees_on_the_map(client):  # noqa: F811
    public = client.get("/api/catalogue").json()
    sign_up(client)
    assert public == {"branches": client.get("/api/map").json()["branches"]}


def test_pro_marks_follow_the_free_plan(client):  # noqa: F811
    branches = {b["id"]: b for b in client.get("/api/catalogue").json()["branches"]}
    marks = {e["id"]: (e["pro"], e["entitled"]) for b in branches.values() for e in b["exercises"]}
    # The fixture's free allowance is one exercise per branch; capstones and projects are Pro.
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


def test_the_counts_match_the_content(client, catalogue):  # noqa: F811
    branches = client.get("/api/catalogue").json()["branches"]
    graph = catalogue.graph
    assert [b["id"] for b in branches] == [
        b.id for b in sorted(graph.branches.values(), key=lambda b: b.order)
    ]
    for branch in branches:
        assert [e["id"] for e in branch["exercises"]] == [
            e.id for e in graph.branch_exercises(branch["id"])
        ]
    assert sum(len(b["exercises"]) for b in branches) == len(graph.exercises)


def test_it_shows_nothing_about_the_caller_or_anyone_else(client, factory, catalogue):  # noqa: F811
    me = sign_up(client)
    pass_(client, factory, catalogue, me, "starter.one")
    saved = client.put(
        "/api/exercises/retrieval.a/draft",
        json={"files": {"solution_mod.py": "SECRET_DRAFT = 1\n"}},
        headers=csrf(me),
    )
    assert saved.status_code == 204, saved.text
    assert client.get("/api/map").json()["branches"][0]["passed_count"] == 1

    # Asked with the learner's own session cookie, and with none.
    body = client.get("/api/catalogue").text
    client.cookies.clear()
    assert client.get("/api/catalogue").text == body

    assert me["email"] not in body
    assert "SECRET_DRAFT" not in body
    branches = client.get("/api/catalogue").json()["branches"]
    assert all(b["passed_count"] == 0 for b in branches)
    statuses = {e["id"]: e["status"] for b in branches for e in b["exercises"]}
    assert statuses["starter.one"] == "available"
    assert "passed" not in statuses.values()
    assert set(branches[0]) == {
        "id", "title", "summary", "unlocked", "requires", "kind", "passed_count", "pro",
        "exercises",
    }  # fmt: skip
