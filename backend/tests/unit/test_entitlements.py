"""The free plan's boundaries: the foundations, the first N of every standard track, never a
capstone, never a guided project."""

import pytest

from lattice.application.plans import unlocks
from lattice.domain.content import Branch, BranchKind, Exercise, PrerequisiteGraph, Tier
from lattice.domain.entitlements import (
    Plan,
    free_exercises,
    is_paid,
    is_pro_exercise,
    may_attempt,
    may_publish_certificates,
)
from lattice.settings import Settings

HASH = "0" * 64


def ex(ex_id: str, *prereqs: str, tier: Tier = Tier.BEGINNER, xp: int = 100) -> Exercise:
    return Exercise(
        id=ex_id,
        version=1,
        title=ex_id,
        branch=ex_id.split(".")[0],
        tier=tier,
        xp=xp,
        prerequisites=prereqs,
        editable=("a.py",),
        checks=({"id": "c", "title": "C", "test": "test_a.py::test_a"},),
        brief="",
        starter_files={"a.py": ""},
        content_hash=HASH,
    )


def chain(branch: str, count: int, *, capstone: bool = False) -> list[Exercise]:
    """`count` exercises in a line, then (optionally) a capstone depending on all of them."""
    items = [ex(f"{branch}.e{i}", *([f"{branch}.e{i - 1}"] if i else ())) for i in range(count)]
    if capstone:
        items.append(ex(f"{branch}.cap", *(e.id for e in items), tier=Tier.CAPSTONE, xp=300))
    return items


def graph(*, track_size: int = 5, capstone: bool = True) -> PrerequisiteGraph:
    return PrerequisiteGraph(
        [
            Branch(id="starter", title="S", summary="", order=0),
            Branch(id="retrieval", title="R", summary="", order=1, requires=("starter",)),
            Branch(
                id="project",
                title="P",
                summary="",
                order=2,
                requires=("starter",),
                kind=BranchKind.PROJECT,
            ),
        ],
        [
            *chain("starter", 6),
            *chain("retrieval", track_size, capstone=capstone),
            *chain("project", 2, capstone=True),
        ],
    )


def test_the_default_allowance_is_three():
    assert Settings.model_fields["free_exercises_per_branch"].default == 3


def test_every_exercise_in_the_root_branch_is_free_however_many_there_are():
    free = free_exercises(graph(), 1)
    assert {f"starter.e{i}" for i in range(6)} <= free


def test_the_first_n_of_a_track_are_free_in_its_stable_order_and_the_rest_are_pro():
    g = graph()
    free = free_exercises(g, 3)
    assert [e.id for e in g.branch_exercises("retrieval") if e.id in free] == [
        "retrieval.e0",
        "retrieval.e1",
        "retrieval.e2",
    ]
    assert is_pro_exercise(g, "retrieval.e3", 3)
    assert is_pro_exercise(g, "retrieval.e4", 3)


@pytest.mark.parametrize("n", [0, 1, 2, 3, 4, 5])
def test_n_sets_the_boundary(n: int):
    free = free_exercises(graph(), n)
    assert sorted(e for e in free if e.startswith("retrieval.")) == [
        f"retrieval.e{i}" for i in range(n)
    ]


def test_a_capstone_is_pro_even_inside_the_allowance():
    g = graph(track_size=1)  # e0, then the capstone second
    assert is_pro_exercise(g, "retrieval.cap", 10)
    assert not is_pro_exercise(g, "retrieval.e0", 10)


def test_every_exercise_of_a_guided_project_is_pro():
    g = graph()
    assert not any(e.startswith("project.") for e in free_exercises(g, 10))
    assert is_pro_exercise(g, "project.e0", 10)


def test_a_negative_allowance_means_only_the_foundations():
    free = free_exercises(graph(), -1)
    assert all(e.startswith("starter.") for e in free)


@pytest.mark.parametrize(
    ("plan", "paid"), [(Plan.FREE, False), (Plan.PRO, True), (Plan.TEAM, True)]
)
def test_pro_and_team_carry_every_entitlement(plan: Plan, paid: bool):
    g = graph()
    assert is_paid(plan) is paid
    assert may_publish_certificates(plan) is paid
    for exercise_id in ("retrieval.cap", "project.e0", "retrieval.e4"):
        assert may_attempt(plan, g, exercise_id, 3) is paid
    for exercise_id in ("starter.e5", "retrieval.e0"):
        assert may_attempt(plan, g, exercise_id, 3)


def graphs_after_retrieval() -> PrerequisiteGraph:
    """Graphs requires Retrieval, which has a capstone: the shape of Knowledge graphs."""
    return PrerequisiteGraph(
        [
            Branch(id="starter", title="S", summary="", order=0),
            Branch(id="retrieval", title="R", summary="", order=1, requires=("starter",)),
            Branch(id="graphs", title="G", summary="", order=2, requires=("retrieval",)),
        ],
        [
            *chain("starter", 1),
            *chain("retrieval", 4, capstone=True),
            *chain("graphs", 4, capstone=True),
        ],
    )


FREE_RETRIEVAL = frozenset({"starter.e0", "retrieval.e0", "retrieval.e1", "retrieval.e2"})


def test_a_free_learner_unlocks_on_every_free_exercise_of_the_required_branch():
    g = graphs_after_retrieval()
    some = FREE_RETRIEVAL - {"retrieval.e2"}
    assert not unlocks(Plan.FREE, g, some, 3).is_branch_unlocked("graphs")
    assert not unlocks(Plan.FREE, g, some, 3).is_available("graphs.e0")

    opens = unlocks(Plan.FREE, g, FREE_RETRIEVAL, 3)
    assert opens.is_branch_unlocked("graphs")
    assert opens.is_available("graphs.e0")
    assert not opens.is_available("graphs.e1")  # its own prerequisite still counts
    assert opens.newly_unlocked(unlocks(Plan.FREE, g, some, 3)) == ("retrieval.e3", "graphs.e0")


def test_pro_exercises_are_judged_on_what_was_passed_even_on_the_free_plan():
    g = graphs_after_retrieval()
    opens = unlocks(Plan.FREE, g, FREE_RETRIEVAL, 3)
    assert opens.is_available("retrieval.e3")  # its prerequisite is passed
    assert not opens.is_available("retrieval.cap")  # retrieval.e3 is not
    passed_graphs = FREE_RETRIEVAL | {"graphs.e0", "graphs.e1", "graphs.e2"}
    assert not unlocks(Plan.FREE, g, passed_graphs, 3).is_available("graphs.e3")


@pytest.mark.parametrize("plan", [Plan.PRO, Plan.TEAM])
def test_a_paid_learner_has_everything_open_whatever_they_have_passed(plan: Plan):
    g = graphs_after_retrieval()
    for passed in (frozenset(), FREE_RETRIEVAL):
        opens = unlocks(plan, g, passed, 3)
        assert opens.is_branch_unlocked("graphs")
        assert all(opens.is_available(i) for i in g.order)
    before = unlocks(plan, g, frozenset(), 3)
    assert unlocks(plan, g, FREE_RETRIEVAL, 3).newly_unlocked(before) == ()
