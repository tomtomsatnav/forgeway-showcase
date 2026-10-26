import pytest
from hypothesis import given
from hypothesis import strategies as st

from lattice.domain.content import ContentError
from lattice.domain.progression import (
    GENERALIST,
    BlockerCode,
    Specialisation,
    TalentNode,
    TalentState,
    TalentTree,
    active_allocations,
    active_titles,
    can_allocate,
    can_deallocate,
    kept_after_path_change,
    node_status,
    points_available,
    points_spent,
    reference_solution_branches,
    talent_points,
)
from lattice.domain.progression.levels import MAX_LEVEL
from tests.unit.test_content_graph import standard_graph

RETRIEVAL = Specialisation(id="retrieval", title="Retrieval", summary="", home_branch="retrieval")


def node(node_id: str, **fields) -> TalentNode:
    fields.setdefault("effects", [{"title": node_id.title()}])
    return TalentNode(id=node_id, title=node_id.title(), summary="", **fields)


def standard_tree() -> TalentTree:
    return TalentTree(
        [RETRIEVAL],
        [
            node("root", min_level=2, required_exercises=["starter.one"]),
            node("kid", parents=["root"], min_level=3, required_exercises=["starter.two"]),
            node(
                "ret",
                subtree="retrieval",
                parents=["root"],  # a specialised node may build on a general one
                min_level=2,
                required_exercises=["retrieval.chunking"],
                effects=[{"reference_solutions": "retrieval"}, {"title": "Archivist"}],
            ),
        ],
        standard_graph(),
    )


def state(level=5, path=GENERALIST, passed=("starter.one", "starter.two"), allocated=()):
    return TalentState(level, path, frozenset(passed), tuple(allocated))


# --- points -----------------------------------------------------------------------------------


def test_one_point_per_level_from_level_two():
    assert [talent_points(n) for n in (1, 2, 3, 10)] == [0, 1, 2, 9]


@given(st.integers(1, MAX_LEVEL))
def test_points_are_never_negative_and_grow_with_level(level):
    assert talent_points(level) >= 0
    assert talent_points(level + 1) == talent_points(level) + 1


# --- validation -------------------------------------------------------------------------------


def test_a_valid_tree_builds():
    tree = standard_tree()
    assert set(tree.nodes) == {"root", "kid", "ret"}
    assert tree.path_ids == (GENERALIST, "retrieval")


def test_every_problem_is_reported_at_once():
    with pytest.raises(ContentError) as caught:
        TalentTree(
            [
                RETRIEVAL,
                Specialisation(id="generalist", title="x", summary="", home_branch="nowhere"),
            ],
            [
                node("a", parents=["ghost"]),
                node("b", subtree="wizardry"),
                node("c", required_exercises=["starter.ghost"]),
                node("d", effects=[{"reference_solutions": "ghost-branch"}]),
                node("e", subtree="retrieval", parents=["f"]),
                node("f", subtree="retrieval"),
                node("g", parents=["e"]),  # a general node cannot build on a class node
                node("loop-1", parents=["loop-2"]),
                node("loop-2", parents=["loop-1"]),
                node("a"),
            ],
            standard_graph(),
        )
    text = "\n".join(caught.value.problems)
    for fragment in (
        "path id 'generalist' is reserved",
        "unknown home branch 'nowhere'",
        "unknown parent 'ghost'",
        "unknown path 'wizardry'",
        "unknown exercise 'starter.ghost'",
        "unknown branch 'ghost-branch'",
        "in a different subtree",
        "talent cycle",
        "defined more than once",
    ):
        assert fragment in text, fragment


def test_a_node_cannot_be_its_own_parent():
    with pytest.raises(ContentError, match="own parent"):
        TalentTree([], [node("a", parents=["a"])], standard_graph())


def test_a_node_needs_an_effect():
    with pytest.raises(ValueError):
        TalentNode(id="a", title="A", summary="", effects=[])


def test_effects_come_from_a_closed_set():
    with pytest.raises(ValueError):
        node("a", effects=[{"xp_multiplier": 2}])


# --- allocation rules -------------------------------------------------------------------------


def codes(tree, node_id, st_):
    return {b.code for b in can_allocate(tree, node_id, st_).blockers}


def test_a_met_node_can_be_allocated():
    assert can_allocate(standard_tree(), "root", state()).allowed


def test_every_reason_a_node_is_blocked_is_given():
    tree = standard_tree()
    assert codes(tree, "kid", state(level=1, passed=())) == {
        BlockerCode.LEVEL,
        BlockerCode.PARENTS,
        BlockerCode.EXERCISES,
        BlockerCode.NO_POINTS,
    }


def test_blocker_details_name_what_is_missing():
    blockers = {
        b.code: b.detail for b in can_allocate(standard_tree(), "kid", state(passed=())).blockers
    }
    assert blockers[BlockerCode.EXERCISES] == "Pass starter.two first."
    assert blockers[BlockerCode.PARENTS] == "Needs Root first."


def test_class_talents_need_that_path():
    tree = standard_tree()
    assert codes(tree, "ret", state(passed=("starter.one", "retrieval.chunking"))) >= {
        BlockerCode.OTHER_PATH
    }
    ok = state(path="retrieval", passed=("retrieval.chunking", "starter.one"), allocated=["root"])
    assert can_allocate(tree, "ret", ok).allowed


def test_an_allocated_node_cannot_be_taken_twice():
    assert codes(standard_tree(), "root", state(allocated=["root"])) == {
        BlockerCode.ALREADY_ALLOCATED
    }


def test_points_cap_how_much_can_be_taken():
    tree = standard_tree()
    at_level_two = state(level=2, allocated=["root"])
    assert points_available(tree, at_level_two) == 0
    assert BlockerCode.NO_POINTS in codes(tree, "kid", at_level_two)


def test_unknown_nodes_are_reported_not_raised():
    assert codes(standard_tree(), "ghost", state()) == {BlockerCode.UNKNOWN_NODE}


def test_a_talent_with_a_dependant_cannot_be_given_back():
    tree = standard_tree()
    st_ = state(allocated=["root", "kid"])
    assert {b.code for b in can_deallocate(tree, "root", st_).blockers} == {BlockerCode.DEPENDANTS}
    assert can_deallocate(tree, "kid", st_).allowed
    assert not can_deallocate(tree, "ret", st_).allowed


def test_node_status_is_allocated_available_or_locked_with_reasons():
    tree = standard_tree()
    st_ = state(allocated=["root"])
    assert node_status(tree, "root", st_).state == "allocated"
    assert node_status(tree, "kid", st_).state == "available"
    locked = node_status(tree, "ret", st_)
    assert locked.state == "locked"
    assert locked.blockers


@given(st.integers(1, 12), st.randoms(use_true_random=False))
def test_greedy_allocation_never_spends_more_than_the_points(level, rng):
    tree = standard_tree()
    st_ = state(level=level, passed=("starter.one", "starter.two", "retrieval.chunking"))
    st_ = TalentState(level, "retrieval", st_.passed, ())
    for _ in range(10):
        options = [n for n in tree.nodes if can_allocate(tree, n, st_).allowed]
        if not options:
            break
        st_ = TalentState(level, "retrieval", st_.passed, (*st_.allocated, rng.choice(options)))
        assert points_spent(tree, st_) <= talent_points(level)
        assert len(active_allocations(tree, st_)) == len(st_.allocated)


# --- content changes and respec ---------------------------------------------------------------


def test_when_over_budget_the_newest_allocations_are_inactive():
    tree = standard_tree()
    over = state(level=2, allocated=["root", "kid"])  # level 2 buys one point
    assert active_allocations(tree, over) == ("root",)
    assert points_spent(tree, over) == 1
    assert points_available(tree, over) == 0
    assert node_status(tree, "kid", over).state == "locked"


def test_allocations_for_removed_or_foreign_nodes_are_inactive():
    tree = standard_tree()
    assert active_allocations(tree, state(allocated=["ghost", "root", "ret"])) == ("root",)


def test_a_child_is_inactive_if_its_parent_is_not_active():
    assert active_allocations(standard_tree(), state(allocated=["kid"])) == ()


def test_changing_path_keeps_general_talents_and_drops_the_old_subtree():
    tree = standard_tree()
    assert kept_after_path_change(tree, ["root", "ret"], GENERALIST) == ("root",)
    assert kept_after_path_change(tree, ["root", "ret"], "retrieval") == ("root", "ret")


def test_switching_to_the_same_path_changes_nothing():
    tree = standard_tree()
    assert kept_after_path_change(tree, ["root", "kid"], GENERALIST) == ("root", "kid")


# --- effects ----------------------------------------------------------------------------------


def test_titles_and_reference_solution_access_come_from_active_talents():
    tree = standard_tree()
    st_ = state(path="retrieval", allocated=["root", "ret"])
    assert active_titles(tree, st_) == ("Root", "Archivist")
    assert reference_solution_branches(tree, st_) == {"retrieval"}


def test_inactive_talents_grant_nothing():
    tree = standard_tree()
    over = state(level=2, path="retrieval", allocated=["root", "ret"])
    assert reference_solution_branches(tree, over) == frozenset()
    assert active_titles(tree, over) == ("Root",)
    assert reference_solution_branches(tree, state()) == frozenset()
