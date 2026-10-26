"""Progression against a real database: badges, learning days, paths, talents and solutions."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import func, select, update

from lattice.application import accounts, grading, progression
from lattice.application.content_sync import sync_content
from lattice.application.errors import (
    ConflictError,
    ForbiddenError,
    InvalidInputError,
    NotFoundError,
)
from lattice.application.learning import total_xp
from lattice.application.streak import files_hash, learning_days, streak_for
from lattice.domain.grading import GradeReport, GradeStatus
from lattice.domain.progression import local_day
from lattice.infrastructure.content_loader import ContentCatalogue, load_catalogue
from lattice.infrastructure.db.engine import transaction
from lattice.infrastructure.db.models import Attempt, BadgeAward, LearnerProfile, TalentAllocation
from tests.content_factory import write_branch, write_exercise
from tests.fakes import ScriptedRunner
from tests.integration.test_learning_flow import (
    CORRECT,
    WRONG,
    attempt_row,
    run_worker_once,
    submit,
)

OTHER_WRONG = {"solution_mod.py": "def add(a, b):\n    return a * b\n"}

CLASSES = """\
paths:
  - {id: retrieval, title: Retrieval, summary: s, home_branch: retrieval}
"""
TALENTS = """\
nodes:
  - id: root
    title: Root
    summary: s
    min_level: 2
    required_exercises: [starter.one]
    effects: [{title: Prompt engineer}]
  - id: kid
    title: Kid
    summary: s
    parents: [root]
    min_level: 2
    required_exercises: [starter.two]
    effects: [{reference_solutions: starter}]
  - id: deep
    title: Deep
    summary: s
    subtree: retrieval
    parents: [root]
    min_level: 2
    required_exercises: [retrieval.chunking]
    effects: [{reference_solutions: retrieval}, {title: Archivist}]
"""
BADGES = """\
badges:
  - id: first-steps
    title: First steps
    description: d
    criterion: {kind: exercises_passed, n: 1}
  - id: right-first-time
    title: Right first time
    description: d
    criterion: {kind: first_try, n: 1}
  - id: foundations
    title: Foundations
    description: d
    criterion: {kind: branch_complete, branch: starter}
  - id: two-days
    title: Two days
    description: d
    criterion: {kind: streak_days, n: 2}
  - id: level-two
    title: Level two
    description: d
    criterion: {kind: level_reached, n: 2}
"""


@pytest.fixture
def catalogue(tmp_path: Path) -> ContentCatalogue:
    """Starter: one (50 XP) -> two (100 XP, hints). Retrieval: chunking (400 XP, with notes).

    Passing everything gives 570 XP, which is level 4 and so three talent points.
    """
    write_branch(tmp_path, "starter", order=0)
    write_branch(tmp_path, "retrieval", order=1, requires=["starter"])
    write_exercise(tmp_path, "starter", "one", xp=50)
    write_exercise(
        tmp_path, "starter", "two", xp=100, prerequisites=["starter.one"], hints=["h1", "h2"]
    )
    chunking = write_exercise(tmp_path, "retrieval", "chunking", xp=400)
    (chunking / "notes.md").write_text("Why the overlap matters.\n")
    progression_dir = tmp_path / "progression"
    progression_dir.mkdir()
    (progression_dir / "classes.yaml").write_text(CLASSES)
    (progression_dir / "talents.yaml").write_text(TALENTS)
    (progression_dir / "badges.yaml").write_text(BADGES)
    return load_catalogue(tmp_path)


@pytest.fixture
def learner(factory, catalogue) -> uuid.UUID:
    with transaction(factory) as session:
        sync_content(session, catalogue.graph)
        user = accounts.register(
            session, email="ada@example.com", password="correct horse battery", display_name="Ada"
        )
        return user.id


def pass_exercise(factory, catalogue, learner, exercise_id: str) -> uuid.UUID:
    attempt_id = submit(factory, catalogue, learner, exercise_id, CORRECT)
    run_worker_once(factory, catalogue)
    return attempt_id


def pass_everything(factory, catalogue, learner) -> None:
    for exercise_id in ("starter.one", "starter.two", "retrieval.chunking"):
        pass_exercise(factory, catalogue, learner, exercise_id)


def backdate(factory, attempt_id: uuid.UUID, days: int) -> None:
    """Move an attempt back in time, as if it had been submitted `days` ago (in UTC)."""
    with transaction(factory) as session:
        row = session.get(Attempt, attempt_id)
        assert row is not None
        then = row.created_at - timedelta(days=days)
        session.execute(
            update(Attempt)
            .where(Attempt.id == attempt_id)
            .values(created_at=then, local_day=local_day(then, ZoneInfo("UTC")))
        )


def badge_ids(factory, learner) -> list[str]:
    with factory() as session:
        return sorted(
            session.scalars(select(BadgeAward.badge_id).where(BadgeAward.user_id == learner))
        )


# --- badges -----------------------------------------------------------------------------------


def test_a_pass_awards_badges_and_reports_them(factory, catalogue, learner):
    attempt_id = pass_exercise(factory, catalogue, learner, "starter.one")

    progression_payload = attempt_row(factory, attempt_id).report["progression"]
    assert [b["id"] for b in progression_payload["badges_awarded"]] == [
        "first-steps",
        "right-first-time",
    ]
    assert progression_payload["badges_awarded"][0]["title"] == "First steps"
    assert progression_payload["streak"] == {"current": 1, "longest": 1}
    assert progression_payload["talent_points_gained"] == 0
    assert badge_ids(factory, learner) == ["first-steps", "right-first-time"]


def test_talent_points_gained_follow_the_level_change(factory, catalogue, learner):
    pass_exercise(factory, catalogue, learner, "starter.one")
    attempt_id = pass_exercise(factory, catalogue, learner, "starter.two")
    payload = attempt_row(factory, attempt_id).report["progression"]
    assert payload["level_after"] == 2
    assert payload["talent_points_gained"] == 1
    assert {b["id"] for b in payload["badges_awarded"]} == {"foundations", "level-two"}


def test_a_badge_is_awarded_once_even_if_the_attempt_is_processed_again(
    factory, catalogue, learner
):
    attempt_id = submit(factory, catalogue, learner, "starter.one", CORRECT)
    with transaction(factory) as session:
        claimed = grading.claim_next(session, "w")
    report = grading.grade(claimed, catalogue, ScriptedRunner())
    for _ in range(2):  # a worker retry delivers the same report twice
        with transaction(factory) as session:
            grading.record_grade(session, catalogue, attempt_id, report, free_per_branch=3)
    # A later pass of a different exercise re-evaluates every badge and must not duplicate.
    pass_exercise(factory, catalogue, learner, "starter.two")

    with factory() as session:
        awards = session.execute(
            select(BadgeAward.badge_id, func.count()).group_by(BadgeAward.badge_id)
        ).all()
        first = session.scalar(
            select(BadgeAward.attempt_id).where(BadgeAward.badge_id == "first-steps")
        )
    assert all(count == 1 for _, count in awards)
    assert first == attempt_id  # credited to the attempt that earned it


def test_evaluating_badges_again_awards_nothing_new(factory, catalogue, learner):
    attempt_id = pass_exercise(factory, catalogue, learner, "starter.one")
    with transaction(factory) as session:
        assert progression.evaluate_badges(session, catalogue, learner, attempt_id) == []


def test_a_failed_attempt_can_earn_a_streak_badge_and_carries_the_payload(
    factory, catalogue, learner
):
    yesterday = submit(factory, catalogue, learner, "starter.one", WRONG)
    run_worker_once(factory, catalogue)
    backdate(factory, yesterday, 1)

    failed = submit(factory, catalogue, learner, "starter.one", OTHER_WRONG)
    run_worker_once(factory, catalogue)

    row = attempt_row(factory, failed)
    assert row.status == "failed"
    payload = row.report["progression"]
    assert payload["xp_awarded"] == 0 and payload["awards"] == [] and payload["unlocked"] == []
    assert payload["level_before"] == payload["level_after"] == 1
    assert [b["id"] for b in payload["badges_awarded"]] == ["two-days"]
    assert payload["streak"] == {"current": 2, "longest": 2}


def test_errored_attempts_earn_nothing_and_do_not_count(factory, catalogue, learner):
    attempt_id = submit(factory, catalogue, learner, "starter.one", CORRECT)
    with transaction(factory) as session:
        grading.claim_next(session, "w")
    errored = GradeReport(status=GradeStatus.ERRORED, error="sandbox fell over")
    with transaction(factory) as session:
        grading.record_grade(session, catalogue, attempt_id, errored, free_per_branch=3)

    row = attempt_row(factory, attempt_id)
    assert row.status == "errored" and "progression" not in row.report
    assert badge_ids(factory, learner) == []
    with factory() as session:
        assert learning_days(session, learner) == frozenset()
        assert streak_for(session, learner).current == 0


# --- learning days ----------------------------------------------------------------------------


def test_a_byte_identical_resubmission_does_not_extend_the_streak(factory, catalogue, learner):
    first = submit(factory, catalogue, learner, "starter.one", WRONG)
    run_worker_once(factory, catalogue)
    backdate(factory, first, 1)

    submit(factory, catalogue, learner, "starter.one", WRONG)  # the very same files, today
    run_worker_once(factory, catalogue)

    with factory() as session:
        days = learning_days(session, learner)
        streak = streak_for(session, learner)
    assert len(days) == 1  # only yesterday counts
    assert streak.current == 1 and streak.longest == 1


def test_a_changed_resubmission_counts(factory, catalogue, learner):
    first = submit(factory, catalogue, learner, "starter.one", WRONG)
    run_worker_once(factory, catalogue)
    backdate(factory, first, 1)

    submit(factory, catalogue, learner, "starter.one", OTHER_WRONG)
    run_worker_once(factory, catalogue)

    with factory() as session:
        assert len(learning_days(session, learner)) == 2
        assert streak_for(session, learner).current == 2


def test_the_same_files_on_a_different_exercise_still_count(factory, catalogue, learner):
    pass_exercise(factory, catalogue, learner, "starter.one")
    two = pass_exercise(factory, catalogue, learner, "starter.two")
    backdate(
        factory, two, 1
    )  # CORRECT was already used for starter.one, but that is another exercise
    with factory() as session:
        assert len(learning_days(session, learner)) == 2


def test_a_duplicate_of_an_errored_attempt_is_new_work(factory, catalogue, learner):
    attempt_id = submit(factory, catalogue, learner, "starter.one", WRONG)
    with transaction(factory) as session:
        grading.claim_next(session, "w")
        grading.record_grade(
            session,
            catalogue,
            attempt_id,
            GradeReport(status=GradeStatus.ERRORED, error="e"),
            free_per_branch=3,
        )
    submit(factory, catalogue, learner, "starter.one", WRONG)
    run_worker_once(factory, catalogue)
    with factory() as session:
        assert len(learning_days(session, learner)) == 1


def test_attempts_are_stamped_with_the_local_day_and_files_hash_at_submission(
    factory, catalogue, learner
):
    with transaction(factory) as session:
        progression.set_time_zone(session, learner, "Pacific/Kiritimati")  # UTC+14
    attempt_id = submit(factory, catalogue, learner, "starter.one", WRONG)
    with transaction(factory) as session:
        progression.set_time_zone(session, learner, "Pacific/Pago_Pago")  # UTC-11

    row = attempt_row(factory, attempt_id)
    assert row.local_day == local_day(row.created_at, ZoneInfo("Pacific/Kiritimati"))
    assert row.files_hash == files_hash(WRONG)
    # Changing the zone afterwards never rewrites history.
    with factory() as session:
        assert session.get(Attempt, attempt_id).local_day == row.local_day


def test_today_is_taken_in_the_learners_current_zone(factory, catalogue, learner):
    attempt_id = submit(factory, catalogue, learner, "starter.one", WRONG)
    run_worker_once(factory, catalogue)
    with transaction(factory) as session:
        session.execute(
            update(Attempt).where(Attempt.id == attempt_id).values(local_day=date(2026, 6, 8))
        )
    instant = datetime(2026, 6, 10, 5, 0, tzinfo=UTC)  # 10 June in UTC, 9 June in Samoa

    with factory() as session:
        assert streak_for(session, learner, now=instant).current == 0  # 8 June is two days back
    with transaction(factory) as session:
        progression.set_time_zone(session, learner, "Pacific/Pago_Pago")
    with factory() as session:
        assert streak_for(session, learner, now=instant).current == 1  # now it is yesterday


def test_time_zones_are_validated_against_zoneinfo(factory, learner):
    with transaction(factory) as session:
        with pytest.raises(InvalidInputError):
            progression.set_time_zone(session, learner, "Mars/Olympus_Mons")
        with pytest.raises(InvalidInputError):
            progression.set_time_zone(session, learner, "../etc/passwd")
        progression.set_time_zone(session, learner, "Europe/London")
    with factory() as session:
        assert session.get(LearnerProfile, learner).time_zone == "Europe/London"


def test_registration_takes_a_time_zone_and_rejects_nonsense(factory):
    with transaction(factory) as session:
        user = accounts.register(
            session, email="a@example.com", password="correct horse battery",
            display_name="A", time_zone="Asia/Tokyo",
        )  # fmt: skip
        assert session.get(LearnerProfile, user.id).time_zone == "Asia/Tokyo"
        with pytest.raises(InvalidInputError):
            accounts.register(
                session, email="b@example.com", password="correct horse battery",
                display_name="B", time_zone="Nowhere/Land",
            )  # fmt: skip


# --- paths and talents ------------------------------------------------------------------------


def test_a_specialisation_needs_the_starter_branch_finished(factory, catalogue, learner):
    pass_exercise(factory, catalogue, learner, "starter.one")
    with transaction(factory) as session:
        with pytest.raises(ForbiddenError, match="Complete Starter first"):
            progression.set_path(session, catalogue, learner, "retrieval", free_per_branch=3)
        # The generalist path is always available.
        progression.set_path(session, catalogue, learner, "generalist", free_per_branch=3)
        with pytest.raises(InvalidInputError):
            progression.set_path(session, catalogue, learner, "wizard", free_per_branch=3)
    pass_exercise(factory, catalogue, learner, "starter.two")
    with transaction(factory) as session:
        progression.set_path(session, catalogue, learner, "retrieval", free_per_branch=3)
    with factory() as session:
        view = progression.profile_view(session, catalogue, learner, free_per_branch=3)
    assert view.path == "retrieval"
    assert [(p.id, p.selectable) for p in view.paths] == [("generalist", True), ("retrieval", True)]


def test_switching_path_drops_the_old_subtree_and_refunds_its_points(factory, catalogue, learner):
    pass_everything(factory, catalogue, learner)
    with transaction(factory) as session:
        progression.set_path(session, catalogue, learner, "retrieval", free_per_branch=3)
        for node in ("root", "deep"):
            progression.allocate_talent(session, catalogue, learner, node)
        view = progression.talent_tree_view(session, catalogue, learner)
    assert (view.total_points, view.spent_points, view.available_points) == (3, 2, 1)

    with transaction(factory) as session:
        dropped = progression.set_path(session, catalogue, learner, "generalist", free_per_branch=3)
        view = progression.talent_tree_view(session, catalogue, learner)
    assert dropped == ("deep",)
    assert {n.node.id: n.status.state for n in view.nodes} == {
        "root": "allocated",
        "kid": "available",
    }
    assert (view.spent_points, view.available_points) == (1, 2)


def test_allocation_enforces_every_rule_with_reasons(factory, catalogue, learner):
    pass_exercise(factory, catalogue, learner, "starter.one")
    with transaction(factory) as session, pytest.raises(ConflictError, match="Needs level 2"):
        progression.allocate_talent(session, catalogue, learner, "root")
    pass_exercise(factory, catalogue, learner, "starter.two")  # level 2: one point
    with transaction(factory) as session:
        with pytest.raises(ConflictError, match="Needs Root first"):
            progression.allocate_talent(session, catalogue, learner, "kid")
        with pytest.raises(ConflictError, match="Retrieval path"):
            progression.allocate_talent(session, catalogue, learner, "deep")
        progression.allocate_talent(session, catalogue, learner, "root")
        with pytest.raises(ConflictError, match="No talent points"):
            progression.allocate_talent(session, catalogue, learner, "kid")
        with pytest.raises(ConflictError, match="Already taken"):
            progression.allocate_talent(session, catalogue, learner, "root")
        with pytest.raises(NotFoundError, match="No talent called"):
            progression.allocate_talent(session, catalogue, learner, "ghost")


def test_deallocation_respec_and_the_budget(factory, catalogue, learner):
    pass_everything(factory, catalogue, learner)
    with transaction(factory) as session:
        for node in ("root", "kid"):
            progression.allocate_talent(session, catalogue, learner, node)
        with pytest.raises(ConflictError, match="builds on this talent"):
            progression.deallocate_talent(session, catalogue, learner, "root")
        progression.deallocate_talent(session, catalogue, learner, "kid")
        with pytest.raises(ConflictError, match="not taken"):
            progression.deallocate_talent(session, catalogue, learner, "kid")
        progression.allocate_talent(session, catalogue, learner, "kid")
        view = progression.respec_talents(session, catalogue, learner)
    assert view.spent_points == 0 and view.available_points == 3
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(TalentAllocation)) == 0


def test_talents_never_change_xp(factory, catalogue, learner):
    pass_everything(factory, catalogue, learner)
    with factory() as session:
        before = total_xp(session, learner)
    with transaction(factory) as session:
        progression.allocate_talent(session, catalogue, learner, "root")
        progression.respec_talents(session, catalogue, learner)
    with factory() as session:
        assert total_xp(session, learner) == before == 570


def test_allocations_for_talents_removed_from_content_are_ignored_then_pruned(
    factory, catalogue, learner
):
    pass_everything(factory, catalogue, learner)
    with transaction(factory) as session:
        session.add(TalentAllocation(user_id=learner, node_id="removed-from-content"))
    with factory() as session:
        view = progression.talent_tree_view(session, catalogue, learner)
    assert (view.spent_points, view.available_points) == (0, 3)

    with transaction(factory) as session:
        progression.allocate_talent(session, catalogue, learner, "root")
    with factory() as session:
        stored = session.scalars(select(TalentAllocation.node_id)).all()
    assert stored == ["root"]


# --- reference solutions ----------------------------------------------------------------------


def test_reference_solutions_are_gated_on_a_pass_and_on_the_talent(factory, catalogue, learner):
    pass_exercise(factory, catalogue, learner, "starter.one")
    with transaction(factory) as session:
        with pytest.raises(ForbiddenError, match="Pass this exercise"):
            progression.reference_solution(session, catalogue, learner, "starter.two")
        with pytest.raises(ForbiddenError, match="Take Kid to unlock it"):
            progression.reference_solution(session, catalogue, learner, "starter.one")

    pass_exercise(factory, catalogue, learner, "starter.two")
    pass_exercise(factory, catalogue, learner, "retrieval.chunking")
    with transaction(factory) as session:
        for node in ("root", "kid"):
            progression.allocate_talent(session, catalogue, learner, node)
        solution = progression.reference_solution(session, catalogue, learner, "starter.one")
        assert solution.files == {"solution_mod.py": "def add(a, b):\n    return a + b\n"}
        # A talent for one branch does not open another. The one that would is named with the
        # path it belongs to, though this learner is not on it.
        with pytest.raises(ForbiddenError, match="This reference solution is locked") as denied:
            progression.reference_solution(session, catalogue, learner, "retrieval.chunking")
        assert denied.value.extensions == {
            "talents": [{"id": "deep", "title": "Deep", "path": "retrieval"}]
        }
        with pytest.raises(NotFoundError, match="No exercise called"):
            progression.reference_solution(session, catalogue, learner, "starter.ghost")


def test_a_talent_on_another_path_or_given_back_no_longer_unlocks_solutions(
    factory, catalogue, learner
):
    pass_everything(factory, catalogue, learner)
    with transaction(factory) as session:
        progression.set_path(session, catalogue, learner, "retrieval", free_per_branch=3)
        progression.allocate_talent(session, catalogue, learner, "root")
        progression.allocate_talent(session, catalogue, learner, "deep")
        solution = progression.reference_solution(session, catalogue, learner, "retrieval.chunking")
        assert solution.notes == "Why the overlap matters.\n"
        progression.set_path(
            session, catalogue, learner, "generalist", free_per_branch=3
        )  # drops `deep`
        with pytest.raises(ForbiddenError):
            progression.reference_solution(session, catalogue, learner, "retrieval.chunking")


def test_learning_days_ignore_other_learners(factory, catalogue, learner):
    with transaction(factory) as session:
        other = accounts.register(
            session, email="bob@example.com", password="correct horse battery", display_name="Bob"
        ).id
    pass_exercise(factory, catalogue, other, "starter.one")
    with factory() as session:
        assert learning_days(session, learner) == frozenset()
