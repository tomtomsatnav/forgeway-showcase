import pytest

from lattice.domain.content import (
    Branch,
    BranchKind,
    ContentError,
    Exercise,
    Isolation,
    Limits,
    PrerequisiteGraph,
    Tier,
)
from lattice.domain.content.graph import REQUIRE_CAPSTONES

HASH = "0" * 64


def make_exercise(ex_id: str, *prereqs: str) -> Exercise:
    return Exercise(
        id=ex_id,
        version=1,
        title=ex_id,
        branch=ex_id.split(".")[0],
        tier="beginner",
        xp=100,
        prerequisites=prereqs,
        editable=("a.py",),
        checks=({"id": "c", "title": "C", "test": "test_a.py::test_a"},),
        brief="",
        starter_files={"a.py": ""},
        content_hash=HASH,
    )


STARTER = Branch(id="starter", title="Starter", summary="", order=0)
RETRIEVAL = Branch(id="retrieval", title="Retrieval", summary="", order=1, requires=("starter",))


def standard_graph() -> PrerequisiteGraph:
    return PrerequisiteGraph(
        [STARTER, RETRIEVAL],
        [
            make_exercise("starter.one"),
            make_exercise("starter.two", "starter.one"),
            make_exercise("retrieval.chunking"),
            make_exercise("retrieval.rag", "retrieval.chunking"),
        ],
    )


def test_first_starter_exercise_is_available_to_a_new_learner():
    graph = standard_graph()
    assert graph.is_available("starter.one", frozenset())
    assert not graph.is_available("starter.two", frozenset())


def test_other_branches_stay_locked_until_the_starter_zone_is_complete():
    graph = standard_graph()
    assert not graph.is_available("retrieval.chunking", frozenset({"starter.one"}))
    assert graph.is_available("retrieval.chunking", frozenset({"starter.one", "starter.two"}))


def test_newly_unlocked_reports_branch_gate_opening():
    graph = standard_graph()
    before = frozenset({"starter.one"})
    after = before | {"starter.two"}
    assert graph.newly_unlocked(before, after) == ("retrieval.chunking",)


def test_order_places_prerequisites_and_gates_first():
    order = standard_graph().order
    assert order.index("starter.two") < order.index("retrieval.chunking")
    assert order.index("retrieval.chunking") < order.index("retrieval.rag")


def test_cycles_are_rejected_with_the_cycle_named():
    with pytest.raises(ContentError, match="prerequisite cycle"):
        PrerequisiteGraph(
            [STARTER],
            [make_exercise("starter.a", "starter.b"), make_exercise("starter.b", "starter.a")],
        )


def test_every_problem_is_reported_not_just_the_first():
    with pytest.raises(ContentError) as info:
        PrerequisiteGraph(
            [Branch(id="x", title="X", summary="", order=0, requires=("missing",))],
            [make_exercise("x.a", "x.ghost"), make_exercise("y.b")],
        )
    problems = "\n".join(info.value.problems)
    assert "unknown branch 'missing'" in problems
    assert "unknown prerequisite 'x.ghost'" in problems
    assert "unknown branch 'y'" in problems


def test_exercise_id_must_match_its_branch():
    with pytest.raises(ValueError, match="must match branch"):
        Exercise.model_validate({**make_exercise("starter.a").model_dump(), "branch": "retrieval"})


def test_isolation_is_always_process():
    assert make_exercise("starter.a").isolation is Isolation.PROCESS
    data = make_exercise("starter.a").model_dump()
    assert Exercise.model_validate({**data, "isolation": "process"}).isolation is Isolation.PROCESS
    for other in ("inprocess", "container"):
        with pytest.raises(ValueError):
            Exercise.model_validate({**data, "isolation": other})


def test_process_isolation_needs_the_python_runtime():
    data = make_exercise("starter.a").model_dump()
    with pytest.raises(ValueError, match="python runtime only"):
        Exercise.model_validate({**data, "isolation": "process", "runtime": "node"})


@pytest.mark.parametrize("path", ["../escape.py", "/etc/passwd", "a\\b.py", ""])
def test_editable_paths_must_be_safe(path: str):
    data = make_exercise("starter.a").model_dump()
    with pytest.raises(ValueError):
        Exercise.model_validate({**data, "editable": (path,), "starter_files": {path: ""}})


def test_order_puts_easier_tiers_first_when_prerequisites_allow():
    hard = make_exercise("starter.hard").model_copy(update={"tier": "advanced"})
    easy = make_exercise("starter.easy", "starter.base")
    graph = PrerequisiteGraph([STARTER], [make_exercise("starter.base"), hard, easy])
    assert graph.order == ("starter.base", "starter.easy", "starter.hard")


# --- Capstones ----------------------------------------------------------------------------------


def make_capstone(ex_id: str, *prereqs: str, xp: int = 350, **limits: int) -> Exercise:
    return make_exercise(ex_id, *prereqs).model_copy(
        update={"tier": Tier.CAPSTONE, "xp": xp, "limits": Limits(**limits)}
    )


def retrieval_graph(*extra: Exercise, require: bool = False) -> PrerequisiteGraph:
    return PrerequisiteGraph(
        [STARTER, RETRIEVAL],
        [
            make_exercise("starter.one"),
            make_exercise("retrieval.chunking"),
            make_exercise("retrieval.rag", "retrieval.chunking"),
            *extra,
        ],
        require_capstones=require,
    )


def problems_of(*extra: Exercise, require: bool = False) -> str:
    with pytest.raises(ContentError) as info:
        retrieval_graph(*extra, require=require)
    return "\n".join(info.value.problems)


def test_a_well_formed_capstone_is_accepted_and_sorts_last_in_its_branch():
    capstone = make_capstone("retrieval.project", "retrieval.rag")
    graph = retrieval_graph(capstone)
    assert graph.branch_exercises("retrieval")[-1].id == "retrieval.project"
    assert graph.order[-1] == "retrieval.project"


def test_a_capstone_sorts_last_even_against_a_costlier_advanced_exercise():
    advanced = make_exercise("retrieval.deep", "retrieval.chunking").model_copy(
        update={"tier": "advanced", "xp": 1000}
    )
    capstone = make_capstone("retrieval.project", "retrieval.rag", "retrieval.deep")
    assert retrieval_graph(advanced, capstone).order[-1] == "retrieval.project"


def test_a_branch_with_two_capstones_is_rejected():
    problems = problems_of(
        make_capstone("retrieval.a", "retrieval.rag"),
        make_capstone("retrieval.b", "retrieval.rag"),
    )
    assert "branch 'retrieval' has 2 capstones: retrieval.a, retrieval.b" in problems


def test_a_capstone_in_the_root_branch_is_rejected():
    with pytest.raises(ContentError, match=r"capstone 'starter\.final' is in 'starter'"):
        PrerequisiteGraph(
            [STARTER], [make_exercise("starter.one"), make_capstone("starter.final", "starter.one")]
        )


def test_a_capstone_must_depend_on_every_other_exercise_in_its_branch():
    problems = problems_of(make_capstone("retrieval.project", "retrieval.chunking"))
    assert "capstone 'retrieval.project' does not depend on every other exercise" in problems
    assert "missing retrieval.rag" in problems


def test_a_capstone_covers_its_branch_through_a_chain_and_ignores_other_branches():
    assert retrieval_graph(make_capstone("retrieval.project", "retrieval.rag"))
    assert retrieval_graph(make_capstone("retrieval.project", "retrieval.rag", "starter.one"))


def test_no_exercise_may_depend_on_a_capstone():
    problems = problems_of(
        make_capstone("retrieval.project", "retrieval.rag"),
        make_exercise("retrieval.after", "retrieval.project"),
    )
    assert "exercise 'retrieval.after' depends on capstone 'retrieval.project'" in problems


@pytest.mark.parametrize("xp", [299, 401])
def test_capstone_xp_must_be_300_to_400(xp: int):
    problems = problems_of(make_capstone("retrieval.project", "retrieval.rag", xp=xp))
    assert f"capstone 'retrieval.project' awards {xp} XP; capstones award 300 to 400" in problems


@pytest.mark.parametrize("xp", [300, 400])
def test_capstone_xp_bounds_are_inclusive(xp: int):
    assert retrieval_graph(make_capstone("retrieval.project", "retrieval.rag", xp=xp))


def test_capstone_limits_are_capped_at_60_seconds_and_512_mb():
    problems = problems_of(
        make_capstone("retrieval.project", "retrieval.rag", timeout_s=61, memory_mb=513)
    )
    assert "allows 61 s; the most is 60 s" in problems
    assert "allows 513 MB; the most is 512 MB" in problems
    assert retrieval_graph(
        make_capstone("retrieval.project", "retrieval.rag", timeout_s=60, memory_mb=512)
    )


def test_every_capstone_violation_is_reported_together():
    problems = problems_of(
        make_capstone("retrieval.a", "retrieval.chunking", xp=10, timeout_s=90),
        make_capstone("retrieval.b", "retrieval.rag", memory_mb=1024),
        make_exercise("retrieval.after", "retrieval.b"),
    )
    for expected in (
        "has 2 capstones",
        "'retrieval.a' does not depend on every other exercise",
        "'retrieval.a' awards 10 XP",
        "'retrieval.a' allows 90 s",
        "'retrieval.b' allows 1024 MB",
        "'retrieval.after' depends on capstone 'retrieval.b'",
    ):
        assert expected in problems, expected


def test_capstones_are_optional_unless_required():
    assert not REQUIRE_CAPSTONES  # the shipped default
    assert retrieval_graph()


def test_with_capstones_required_every_branch_that_requires_another_needs_one():
    problems = problems_of(require=True)
    assert "branch 'retrieval' has no capstone" in problems
    assert "branch 'starter' has no capstone" not in problems  # the root branch is exempt
    assert retrieval_graph(make_capstone("retrieval.project", "retrieval.rag"), require=True)


def test_capstone_checks_tolerate_unknown_prerequisites():
    problems = problems_of(make_capstone("retrieval.project", "retrieval.ghost"))
    assert "unknown prerequisite 'retrieval.ghost'" in problems


# --- Carrying files forward, and project branches -----------------------------------------------


def carrying(ex_id: str, source: str, *prereqs: str) -> Exercise:
    return make_exercise(ex_id, *prereqs).model_copy(update={"carry_from": source})


def test_an_exercise_may_carry_files_from_one_it_depends_on_through_a_chain():
    graph = retrieval_graph(
        make_exercise("retrieval.serve", "retrieval.rag"),
        carrying("retrieval.deploy", "retrieval.chunking", "retrieval.serve"),
    )
    assert graph.exercises["retrieval.deploy"].carry_from == "retrieval.chunking"


def test_an_exercise_cannot_carry_files_from_itself():
    with pytest.raises(ValueError, match="cannot carry files from itself"):
        Exercise.model_validate(
            {**make_exercise("retrieval.rag").model_dump(), "carry_from": "retrieval.rag"}
        )


def test_carry_from_must_name_an_earlier_exercise_in_the_same_branch_that_it_depends_on():
    problems = problems_of(
        carrying("retrieval.a", "retrieval.ghost", "retrieval.rag"),
        carrying("retrieval.b", "starter.one", "starter.one"),
        carrying("retrieval.c", "retrieval.rag"),
    )
    assert "exercise 'retrieval.a' carries from unknown exercise 'retrieval.ghost'" in problems
    assert "exercise 'retrieval.b' carries from 'starter.one' in another branch" in problems
    assert (
        "exercise 'retrieval.c' carries from 'retrieval.rag' but does not depend on it" in problems
    )


def test_a_project_branch_must_require_another_branch():
    lone = Branch(id="solo", title="Solo", summary="", order=0, kind=BranchKind.PROJECT)
    with pytest.raises(ContentError, match="project branch 'solo' requires no other branch"):
        PrerequisiteGraph([lone], [make_exercise("solo.one")])
    project = RETRIEVAL.model_copy(update={"kind": BranchKind.PROJECT})
    assert PrerequisiteGraph(
        [STARTER, project], [make_exercise("starter.one"), make_exercise("retrieval.a")]
    )


def test_branch_kind_defaults_to_standard_and_rejects_unknown_kinds():
    assert STARTER.kind is BranchKind.STANDARD
    as_project = Branch.model_validate({**STARTER.model_dump(), "kind": "project"})
    assert as_project.kind is BranchKind.PROJECT
    with pytest.raises(ValueError, match="kind"):
        Branch.model_validate({**STARTER.model_dump(), "kind": "expedition"})


PRIMER = Branch(id="primer", title="Primer", summary="s", order=9, kind=BranchKind.PRIMER)
LEARN = Branch(id="learn", title="Learn", summary="s", order=1, requires=("starter",))


def primer_graph(*extra: Exercise, branches: tuple[Branch, ...] = (), require: bool = True):
    return PrerequisiteGraph(
        [
            Branch(id="starter", title="Starter", summary="s", order=0),
            PRIMER,
            *branches,
        ],
        [make_exercise("starter.one"), make_exercise("primer.a"), *extra],
        require_capstones=require,
    )


def test_a_primer_needs_no_capstone_and_is_outside_the_requirement():
    graph = primer_graph()
    assert graph.is_available("primer.a", frozenset())
    assert graph.is_branch_complete("starter", frozenset({"starter.one"}))


def test_the_capstone_requirement_still_binds_the_other_branches_beside_a_primer():
    with pytest.raises(ContentError, match="branch 'learn' has no capstone"):
        primer_graph(make_exercise("learn.x"), branches=(LEARN,))


def test_a_primer_exercise_cannot_be_a_capstone():
    capstone = make_exercise("primer.big", "primer.a").model_copy(
        update={"tier": Tier.CAPSTONE, "xp": 300}
    )
    with pytest.raises(ContentError, match="requires nothing"):
        primer_graph(capstone)


def test_a_primer_requires_nothing():
    needy = Branch(id="primer", title="P", summary="s", order=1, requires=("starter",),
                   kind=BranchKind.PRIMER)  # fmt: skip
    with pytest.raises(ContentError, match="primer branch 'primer' must require nothing"):
        PrerequisiteGraph(
            [Branch(id="starter", title="S", summary="s", order=0), needy],
            [make_exercise("starter.one"), make_exercise("primer.a")],
        )


def test_no_branch_may_require_a_primer():
    needs_primer = Branch(id="learn", title="L", summary="s", order=1, requires=("primer",))
    with pytest.raises(ContentError, match="branch 'learn' requires primer branch 'primer'"):
        primer_graph(make_exercise("learn.x"), branches=(needs_primer,), require=False)


def test_no_exercise_outside_a_primer_may_depend_on_one():
    with pytest.raises(ContentError, match=r"depends on primer exercise 'primer\.a'"):
        primer_graph(make_exercise("starter.two", "primer.a"))
    # Inside the primer, order is the author's to choose.
    assert primer_graph(make_exercise("primer.b", "primer.a")).exercises["primer.b"]


def test_passing_a_primer_changes_nothing_for_the_other_branches():
    capstone = make_exercise("learn.cap", "learn.x").model_copy(
        update={"tier": Tier.CAPSTONE, "xp": 300}
    )
    graph = primer_graph(make_exercise("learn.x"), capstone, branches=(LEARN,))
    assert not graph.is_available("learn.x", frozenset({"primer.a"}))
    assert graph.is_available("learn.x", frozenset({"starter.one"}))
    assert graph.newly_unlocked(frozenset(), frozenset({"primer.a"})) == ()


def test_a_primer_comes_after_everything_else_in_the_stable_order():
    graph = primer_graph(make_exercise("learn.x"), branches=(LEARN,), require=False)
    assert graph.order == ("starter.one", "learn.x", "primer.a")
