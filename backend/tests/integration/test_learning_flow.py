"""The learner journey against a real database: submit, grade, earn XP, unlock."""

from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from lattice.application import accounts, grading, learning
from lattice.application.content_sync import current_revision_ids, sync_content
from lattice.application.errors import (
    AttemptCapError,
    AttemptInFlightError,
    ConflictError,
    ForbiddenError,
    GradingBudgetError,
    InvalidInputError,
    RateLimitedError,
    ServiceBusyError,
)
from lattice.infrastructure.db.engine import transaction
from lattice.infrastructure.db.models import Attempt, ExerciseRevision, XpEvent
from tests.fakes import ScriptedRunner

CORRECT = {"solution_mod.py": "def add(a, b):\n    return a + b\n"}
WRONG = {"solution_mod.py": "def add(a, b):\n    return a - b\n"}


@pytest.fixture
def learner(factory, catalogue) -> uuid.UUID:
    with transaction(factory) as session:
        sync_content(session, catalogue.graph)
        user = accounts.register(
            session, email="Ada@Example.com", password="correct horse battery", display_name="Ada"
        )
        return user.id


def submit(
    factory,
    catalogue,
    user_id,
    exercise_id,
    files,
    limit=10,
    per_day=None,
    queue_depth=None,
    budget_s=None,
) -> uuid.UUID:
    with transaction(factory) as session:
        revisions = current_revision_ids(session)
        attempt = learning.submit_attempt(
            session,
            catalogue,
            revisions,
            user_id,
            exercise_id,
            files,
            per_minute_limit=limit,
            per_day_limit=per_day,
            max_queue_depth=queue_depth,
            grading_seconds_per_day=budget_s,
            free_per_branch=3,
        )
        return attempt.id


def other_learner(factory, email: str) -> uuid.UUID:
    with transaction(factory) as session:
        return accounts.register(
            session, email=email, password="correct horse battery", display_name="B"
        ).id


def run_worker_once(factory, catalogue, runner=None, free_per_branch=3) -> uuid.UUID | None:
    with transaction(factory) as session:
        claimed = grading.claim_next(session, "worker-test")
    if claimed is None:
        return None
    report = grading.grade(claimed, catalogue, runner or ScriptedRunner())
    with transaction(factory) as session:
        grading.record_grade(
            session, catalogue, claimed.id, report, free_per_branch=free_per_branch
        )
    return claimed.id


def attempt_row(factory, attempt_id) -> Attempt:
    with factory() as session:
        return session.get(Attempt, attempt_id)


def test_new_learner_sees_only_the_first_exercise_available(factory, catalogue, learner):
    with factory() as session:
        view = learning.learner_map(session, catalogue, learner, free_per_branch=3)
    statuses = {e.id: e.status for b in view.branches for e in b.exercises}
    assert statuses == {
        "starter.one": "available",
        "starter.two": "locked",
        "retrieval.chunking": "locked",
    }
    assert view.level.level == 1


def test_locked_exercises_cannot_be_submitted(factory, catalogue, learner):
    with pytest.raises(ForbiddenError):
        submit(factory, catalogue, learner, "starter.two", CORRECT)


def test_failed_attempt_reports_checks_and_awards_nothing(factory, catalogue, learner):
    attempt_id = submit(factory, catalogue, learner, "starter.one", WRONG)
    run_worker_once(factory, catalogue)

    row = attempt_row(factory, attempt_id)
    assert row.status == "failed"
    assert row.report["checks"][0]["message"] == "nope"
    with factory() as session:
        assert learning.total_xp(session, learner) == 0


def test_passing_awards_xp_once_and_unlocks_the_next_exercise(factory, catalogue, learner):
    attempt_id = submit(factory, catalogue, learner, "starter.one", CORRECT)
    run_worker_once(factory, catalogue)

    progression = attempt_row(factory, attempt_id).report["progression"]
    assert progression["xp_awarded"] == 50  # starter.one has no hints, so no bonus
    assert progression["unlocked"] == ["starter.two"]

    # Resubmitting a passed exercise is allowed but earns nothing.
    again = submit(factory, catalogue, learner, "starter.one", CORRECT)
    run_worker_once(factory, catalogue)
    assert attempt_row(factory, again).report["progression"]["xp_awarded"] == 0
    with factory() as session:
        assert learning.total_xp(session, learner) == 50


def test_no_hint_bonus_is_forfeited_by_revealing_a_hint(factory, catalogue, learner):
    submit(factory, catalogue, learner, "starter.one", CORRECT)
    run_worker_once(factory, catalogue)
    with transaction(factory) as session:
        hints = learning.reveal_next_hint(
            session, catalogue, learner, "starter.two", free_per_branch=3
        )
    assert hints == ("h1",)

    attempt_id = submit(factory, catalogue, learner, "starter.two", CORRECT)
    run_worker_once(factory, catalogue)
    awards = attempt_row(factory, attempt_id).report["progression"]["awards"]
    assert awards == [{"reason": "passed", "amount": 100}]


def test_completing_the_starter_branch_unlocks_retrieval(factory, catalogue, learner):
    for exercise_id in ("starter.one", "starter.two"):
        last = submit(factory, catalogue, learner, exercise_id, CORRECT)
        run_worker_once(factory, catalogue)
    progression = attempt_row(factory, last).report["progression"]
    assert progression["unlocked"] == ["retrieval.chunking"]
    assert progression["xp_awarded"] == 120  # 100 + 20% no-hint bonus
    assert progression["level_before"] == 1 and progression["level_after"] == 2


def test_only_one_attempt_per_learner_may_be_in_flight(factory, catalogue, learner):
    submit(factory, catalogue, learner, "starter.one", CORRECT)
    with pytest.raises(AttemptInFlightError, match="already have an attempt being graded"):
        submit(factory, catalogue, learner, "starter.one", WRONG)
    run_worker_once(factory, catalogue)
    submit(factory, catalogue, learner, "starter.two", WRONG)
    # Across exercises too.
    with pytest.raises(ConflictError, match="already have an attempt being graded"):
        submit(factory, catalogue, learner, "starter.one", WRONG)
    run_worker_once(factory, catalogue)
    submit(factory, catalogue, learner, "starter.one", WRONG)


def test_the_database_refuses_a_second_attempt_in_flight(factory, catalogue, learner):
    """The unique index backs the check, for two submissions racing past it."""
    submit(factory, catalogue, learner, "starter.one", WRONG)
    with factory() as session, session.begin():
        first = session.scalars(select(Attempt)).one()
        session.add(
            Attempt(
                user_id=learner,
                exercise_id="starter.two",
                revision_id=first.revision_id,
                files=WRONG,
                local_day=first.local_day,
                status="queued",
            )
        )
        with pytest.raises(IntegrityError):
            session.flush()


def test_a_daily_cap_limits_attempts_per_learner(factory, catalogue, learner):
    for _ in range(2):
        submit(factory, catalogue, learner, "starter.one", WRONG, per_day=2)
        run_worker_once(factory, catalogue)
    with pytest.raises(AttemptCapError, match="today's 2 graded attempts") as refused:
        submit(factory, catalogue, learner, "starter.one", WRONG, per_day=2)
    assert refused.value.extensions == {"limit": 2}
    # Attempts from more than 24 hours ago, and errored ones, no longer count.
    with transaction(factory) as session:
        oldest = session.scalars(select(Attempt).order_by(Attempt.created_at)).first()
        oldest.created_at = datetime.now(UTC) - timedelta(days=1, minutes=1)
    submit(factory, catalogue, learner, "starter.one", WRONG, per_day=2)
    with transaction(factory) as session:
        session.execute(update(Attempt).values(status="errored"))
    submit(factory, catalogue, learner, "starter.one", WRONG, per_day=2)


def slow_runner(seconds: int) -> ScriptedRunner:
    """A runner whose every run is recorded as taking `seconds`, as a deliberate timeout is."""
    runner = ScriptedRunner()
    run = runner.run

    def timed(request):
        return replace(run(request), duration_ms=seconds * 1000)

    runner.run = timed  # type: ignore[method-assign]
    return runner


def test_a_daily_grading_time_budget_limits_each_learner(factory, catalogue, learner):
    # Two runs of 50 s use the 100 s budget; the attempt cap (unset) never comes into it.
    for _ in range(2):
        submit(factory, catalogue, learner, "starter.one", WRONG, budget_s=100)
        run_worker_once(factory, catalogue, slow_runner(50))
    with pytest.raises(GradingBudgetError, match="today's 1 minutes of grading time") as refused:
        submit(factory, catalogue, learner, "starter.one", WRONG, budget_s=100)
    assert refused.value.code == "grading-budget"
    assert refused.value.extensions == {"budget_minutes": 1}
    with factory() as session:
        assert learning.grading_seconds_since(
            session, learner, datetime.now(UTC) - timedelta(days=1)
        ) == pytest.approx(100)
    # Another learner has their own budget.
    other = other_learner(factory, "b@example.com")
    submit(factory, catalogue, other, "starter.one", WRONG, budget_s=100)
    # Runs from more than 24 hours ago no longer count.
    with transaction(factory) as session:
        oldest = session.scalars(
            select(Attempt).where(Attempt.user_id == learner).order_by(Attempt.created_at)
        ).first()
        oldest.created_at = datetime.now(UTC) - timedelta(days=1, minutes=1)
    submit(factory, catalogue, learner, "starter.one", WRONG, budget_s=100)


def test_a_full_queue_refuses_new_attempts(factory, catalogue, learner):
    submit(factory, catalogue, learner, "starter.one", WRONG, queue_depth=1)
    other = other_learner(factory, "b@example.com")
    with pytest.raises(ServiceBusyError, match="very busy"):
        submit(factory, catalogue, other, "starter.one", WRONG, queue_depth=1)
    run_worker_once(factory, catalogue)
    submit(factory, catalogue, other, "starter.one", WRONG, queue_depth=1)


def test_submissions_are_rate_limited(factory, catalogue, learner):
    for _ in range(2):
        submit(factory, catalogue, learner, "starter.one", WRONG, limit=2)
        run_worker_once(factory, catalogue)
    with pytest.raises(RateLimitedError):
        submit(factory, catalogue, learner, "starter.one", WRONG, limit=2)


def test_non_editable_files_are_rejected(factory, catalogue, learner):
    with pytest.raises(InvalidInputError, match="cannot be edited"):
        submit(factory, catalogue, learner, "starter.one", {"conftest.py": "x"})


def test_recording_the_same_grade_twice_is_harmless(factory, catalogue, learner):
    attempt_id = submit(factory, catalogue, learner, "starter.one", CORRECT)
    with transaction(factory) as session:
        claimed = grading.claim_next(session, "w")
    report = grading.grade(claimed, catalogue, ScriptedRunner())
    for _ in range(2):
        with transaction(factory) as session:
            grading.record_grade(session, catalogue, attempt_id, report, free_per_branch=3)
    with factory() as session:
        events = session.scalars(select(XpEvent).where(XpEvent.user_id == learner)).all()
    assert len(events) == 1


def test_concurrent_workers_never_claim_the_same_attempt(factory, catalogue, learner):
    submit(factory, catalogue, learner, "starter.one", WRONG)
    first = factory()
    second = factory()
    with first.begin(), second.begin():
        a = grading.claim_next(first, "w1")
        b = grading.claim_next(second, "w2")
    assert a is not None and b is None
    first.close()
    second.close()


def test_stale_running_attempts_are_requeued_then_given_up(factory, catalogue, learner):
    attempt_id = submit(factory, catalogue, learner, "starter.one", WRONG)
    with transaction(factory) as session:
        grading.claim_next(session, "dead-worker")
        session.execute(
            update(Attempt).values(claimed_at=datetime.now(UTC) - timedelta(minutes=10))
        )
    with transaction(factory) as session:
        grading.requeue_stale(session, visibility_timeout=timedelta(minutes=2), max_tries=2)
    assert attempt_row(factory, attempt_id).status == "queued"

    with transaction(factory) as session:
        grading.claim_next(session, "dead-again")
        session.execute(
            update(Attempt).values(claimed_at=datetime.now(UTC) - timedelta(minutes=10))
        )
    with transaction(factory) as session:
        grading.requeue_stale(session, visibility_timeout=timedelta(minutes=2), max_tries=2)
    row = attempt_row(factory, attempt_id)
    assert row.status == "errored"
    assert "does not count against you" in row.report["error"]


def test_drafts_are_saved_and_returned_with_the_exercise(factory, catalogue, learner):
    with transaction(factory) as session:
        learning.save_draft(
            session, catalogue, learner, "starter.one", {"solution_mod.py": "# wip"}
        )
    with factory() as session:
        view = learning.exercise_view(session, catalogue, learner, "starter.one", free_per_branch=3)
    assert view.files == {"solution_mod.py": "# wip"}


def test_content_sync_is_idempotent_and_versions_changed_content(factory, catalogue):
    with transaction(factory) as session:
        assert sync_content(session, catalogue.graph).new_revisions == 3
    with transaction(factory) as session:
        assert sync_content(session, catalogue.graph).new_revisions == 0

    changed = catalogue.graph.exercises["starter.one"].model_copy(update={"content_hash": "f" * 64})
    graph = type(catalogue.graph)(
        catalogue.graph.branches.values(),
        [changed, *(e for i, e in catalogue.graph.exercises.items() if i != "starter.one")],
    )
    with transaction(factory) as session:
        assert sync_content(session, graph).new_revisions == 1
    with factory() as session:
        rows = session.scalars(
            select(ExerciseRevision).where(ExerciseRevision.exercise_id == "starter.one")
        ).all()
    assert sorted(r.is_current for r in rows) == [False, True]
