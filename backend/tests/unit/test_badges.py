import pytest
from hypothesis import given
from hypothesis import strategies as st

from lattice.domain.progression import Badge, LearnerFacts, badge_problems, newly_earned


def badge(badge_id: str, **criterion) -> Badge:
    return Badge.model_validate(
        {"id": badge_id, "title": badge_id.title(), "description": "d", "criterion": criterion}
    )


def facts(**overrides) -> LearnerFacts:
    base = {
        "completed_branches": frozenset(),
        "exercises_passed": 0,
        "first_try_passes": 0,
        "no_hint_passes": 0,
        "longest_streak": 0,
        "level": 1,
        "capstones_passed": 0,
    }
    return LearnerFacts(**{**base, **overrides})


CRITERIA = [
    (
        {"kind": "branch_complete", "branch": "starter"},
        {"completed_branches": frozenset({"starter"})},
    ),
    ({"kind": "exercises_passed", "n": 3}, {"exercises_passed": 3}),
    ({"kind": "first_try", "n": 2}, {"first_try_passes": 2}),
    ({"kind": "no_hint_passes", "n": 4}, {"no_hint_passes": 4}),
    ({"kind": "streak_days", "n": 5}, {"longest_streak": 5}),
    ({"kind": "level_reached", "n": 6}, {"level": 6}),
    ({"kind": "capstones_passed", "n": 2}, {"capstones_passed": 2}),
]


@pytest.mark.parametrize(("criterion", "enough"), CRITERIA)
def test_each_criterion_is_met_exactly_at_its_threshold(criterion, enough):
    b = badge("b", **criterion)
    assert newly_earned(facts(), [], [b]) == []
    assert newly_earned(facts(**enough), [], [b]) == [b]


@pytest.mark.parametrize(("criterion", "enough"), CRITERIA)
def test_every_criterion_describes_itself(criterion, enough):
    description = badge("b", **criterion).criterion.describe({"starter": "Foundations"})
    assert description.endswith(".") and len(description) > 8


def test_branch_descriptions_use_the_branch_title():
    c = badge("b", kind="branch_complete", branch="starter").criterion
    assert c.describe({"starter": "Foundations"}) == "Pass every exercise in Foundations."


def test_a_missing_one_less_than_the_threshold_does_not_earn_it():
    b = badge("b", kind="exercises_passed", n=3)
    assert newly_earned(facts(exercises_passed=2), [], [b]) == []


def test_already_awarded_badges_are_not_awarded_again():
    first = badge("first", kind="exercises_passed", n=1)
    second = badge("second", kind="exercises_passed", n=2)
    got = newly_earned(facts(exercises_passed=2), ["first"], [first, second])
    assert got == [second]


def test_several_badges_can_be_earned_by_one_attempt_in_definition_order():
    a, b = badge("a", kind="level_reached", n=2), badge("b", kind="exercises_passed", n=1)
    assert newly_earned(facts(level=2, exercises_passed=1), [], [a, b]) == [a, b]


def test_unknown_criteria_and_extra_fields_are_rejected():
    with pytest.raises(ValueError):
        badge("b", kind="logged_in", n=1)
    with pytest.raises(ValueError):
        badge("b", kind="exercises_passed", n=1, bonus=True)
    with pytest.raises(ValueError):
        badge("b", kind="exercises_passed", n=0)


def test_problems_name_duplicates_and_unknown_branches():
    problems = badge_problems(
        [
            badge("a", kind="branch_complete", branch="ghost"),
            badge("a", kind="exercises_passed", n=1),
        ],
        branches=["starter"],
    )
    assert len(problems) == 2
    assert any("unknown branch 'ghost'" in p for p in problems)
    assert any("more than once" in p for p in problems)


counts = st.integers(0, 50)


@given(
    counts,
    counts,
    counts,
    counts,
    st.integers(1, 60),
    counts,
    counts,
    counts,
    counts,
    st.integers(1, 60),
)
def test_better_facts_never_lose_a_badge(p1, f1, h1, s1, l1, dp, df, dh, ds, dl):
    """Criteria are monotone: gaining progress can only earn more."""
    all_badges = [badge(f"b{i}", **c) for i, (c, _) in enumerate(CRITERIA)]
    before = facts(
        completed_branches=frozenset(),
        exercises_passed=p1,
        first_try_passes=f1,
        no_hint_passes=h1,
        longest_streak=s1,
        level=l1,
    )
    after = facts(
        completed_branches=frozenset({"starter"}),
        exercises_passed=p1 + dp,
        first_try_passes=f1 + df,
        no_hint_passes=h1 + dh,
        longest_streak=s1 + ds,
        level=l1 + dl,
    )
    earned_before = {b.id for b in newly_earned(before, [], all_badges)}
    earned_after = {b.id for b in newly_earned(after, [], all_badges)}
    assert earned_before <= earned_after
