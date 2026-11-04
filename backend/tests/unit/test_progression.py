import pytest
from hypothesis import given
from hypothesis import strategies as st

from lattice.domain.progression import (
    XpReason,
    awards_for_pass,
    level_progress,
    xp_threshold,
)
from lattice.domain.progression.levels import MAX_LEVEL
from tests.unit.test_content_graph import make_exercise


def test_first_pass_without_hints_earns_base_plus_bonus():
    exercise = make_exercise("starter.a").model_copy(update={"xp": 100, "hints": ("h1", "h2")})
    awards = awards_for_pass(exercise, hints_revealed=0, previously_passed=False)
    assert [(a.reason, a.amount) for a in awards] == [
        (XpReason.PASSED, 100),
        (XpReason.NO_HINTS, 20),
    ]


def test_revealing_a_hint_forfeits_only_the_bonus():
    exercise = make_exercise("starter.a").model_copy(update={"xp": 100, "hints": ("h1",)})
    awards = awards_for_pass(exercise, hints_revealed=1, previously_passed=False)
    assert [(a.reason, a.amount) for a in awards] == [(XpReason.PASSED, 100)]


def test_exercises_without_hints_carry_no_bonus():
    awards = awards_for_pass(make_exercise("starter.a"), hints_revealed=0, previously_passed=False)
    assert [a.reason for a in awards] == [XpReason.PASSED]


def test_resubmitting_a_passed_exercise_earns_nothing():
    assert (
        awards_for_pass(make_exercise("starter.a"), hints_revealed=0, previously_passed=True) == []
    )


def test_level_thresholds_match_the_documented_curve():
    assert [xp_threshold(n) for n in (1, 2, 5)] == [0, 100, 800]


@given(st.integers(min_value=0, max_value=1_000_000))
def test_level_is_the_highest_whose_threshold_is_reached(total):
    progress = level_progress(total)
    assert xp_threshold(progress.level) <= total
    if progress.level < MAX_LEVEL:
        assert xp_threshold(progress.level + 1) > total
        assert 0.0 <= progress.fraction < 1.0


@given(st.integers(min_value=0, max_value=500_000), st.integers(min_value=0, max_value=5_000))
def test_more_xp_never_means_a_lower_level(total, extra):
    assert level_progress(total + extra).level >= level_progress(total).level


def test_negative_xp_is_rejected():
    with pytest.raises(ValueError):
        level_progress(-1)
