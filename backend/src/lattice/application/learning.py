"""Learner-facing use cases: the map of branches, exercises, hints, drafts and submissions."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from lattice.application import plans
from lattice.application.errors import (
    AttemptCapError,
    AttemptInFlightError,
    ConflictError,
    ForbiddenError,
    GradingBudgetError,
    InvalidInputError,
    NotFoundError,
    RateLimitedError,
    ServiceBusyError,
)
from lattice.application.streak import files_hash, learner_zone, streak_for
from lattice.domain.content import BranchKind, Exercise
from lattice.domain.entitlements import free_exercises, is_paid
from lattice.domain.grading import SubmissionError
from lattice.domain.grading.service import validate_submission
from lattice.domain.progression import LevelProgress, Streak, level_progress, local_day
from lattice.infrastructure.content_loader import ContentCatalogue
from lattice.infrastructure.db.models import Attempt, Draft, ExerciseProgress, User, XpEvent

ExerciseStatus = Literal["locked", "available", "passed"]
# Where the workspace's files came from: the starter, the learner's draft, or their passing files
# from the exercise named by `carry_from`.
FilesSource = Literal["starter", "draft", "carried"]
RECENT_ATTEMPTS = 10


@dataclass(frozen=True)
class ExerciseSummary:
    id: str
    title: str
    tier: str
    xp: int
    skills: tuple[str, ...]
    prerequisites: tuple[str, ...]
    status: ExerciseStatus
    pro: bool = False  # outside the free plan
    entitled: bool = True  # the learner's plan lets them attempt it (prerequisites aside)


@dataclass(frozen=True)
class BranchView:
    id: str
    title: str
    summary: str
    unlocked: bool
    requires: tuple[str, ...]
    kind: BranchKind
    exercises: tuple[ExerciseSummary, ...]

    @property
    def passed_count(self) -> int:
        return sum(1 for e in self.exercises if e.status == "passed")

    @property
    def pro(self) -> bool:
        """Every exercise in the branch is Pro (a guided project, say)."""
        return all(e.pro for e in self.exercises)


@dataclass(frozen=True)
class LearnerMap:
    branches: tuple[BranchView, ...]
    level: LevelProgress
    streak: Streak


@dataclass(frozen=True)
class ExerciseView:
    exercise: Exercise
    status: ExerciseStatus
    hints_revealed: tuple[str, ...]
    files: dict[str, str]  # the learner's draft, carried files, or the starter files
    files_source: FilesSource = "starter"
    carried_from: str | None = None  # set when `files_source` is "carried"
    recent_attempts: tuple[Attempt, ...] = field(default=())
    pro: bool = False
    entitled: bool = True


def passed_exercises(session: Session, user_id: uuid.UUID) -> frozenset[str]:
    rows = session.scalars(
        select(ExerciseProgress.exercise_id).where(
            ExerciseProgress.user_id == user_id, ExerciseProgress.first_passed_at.is_not(None)
        )
    )
    return frozenset(rows)


def total_xp(session: Session, user_id: uuid.UUID) -> int:
    return (
        session.scalar(
            select(func.coalesce(func.sum(XpEvent.amount), 0)).where(XpEvent.user_id == user_id)
        )
        or 0
    )


def status_of(
    catalogue: ContentCatalogue,
    exercise_id: str,
    passed: frozenset[str],
    opens: plans.Unlocks | None = None,
) -> ExerciseStatus:
    """Passed on the learner's own record; available when `opens` (the learner's plan-aware
    unlocks, `learner_unlocks`) says so, or by prerequisites alone when it is not given."""
    if exercise_id in passed:
        return "passed"
    available = (
        catalogue.graph.is_available(exercise_id, passed)
        if opens is None
        else opens.is_available(exercise_id)
    )
    return "available" if available else "locked"


def learner_unlocks(
    session: Session,
    catalogue: ContentCatalogue,
    user_id: uuid.UUID,
    passed: frozenset[str],
    *,
    free_per_branch: int,
) -> plans.Unlocks:
    """What this learner may open on their plan, given what they have passed."""
    plan = plans.plan_of(_learner(session, user_id))
    return plans.unlocks(plan, catalogue.graph, passed, free_per_branch)


def _learner(session: Session, user_id: uuid.UUID) -> User:
    user = session.get(User, user_id)
    if user is None:
        raise NotFoundError("No such learner.")
    return user


def learner_map(
    session: Session,
    catalogue: ContentCatalogue,
    user_id: uuid.UUID,
    *,
    free_per_branch: int,
) -> LearnerMap:
    """Every branch and exercise with the learner's status and entitlement, plus their level."""
    graph = catalogue.graph
    passed = passed_exercises(session, user_id)
    free = free_exercises(graph, free_per_branch)
    paid = is_paid(plans.plan_of(_learner(session, user_id)))
    opens = learner_unlocks(session, catalogue, user_id, passed, free_per_branch=free_per_branch)
    branches = tuple(
        BranchView(
            id=branch.id,
            title=branch.title,
            summary=branch.summary,
            unlocked=opens.is_branch_unlocked(branch.id),
            requires=branch.requires,
            kind=branch.kind,
            exercises=tuple(
                ExerciseSummary(
                    id=ex.id,
                    title=ex.title,
                    tier=ex.tier.value,
                    xp=ex.xp,
                    skills=ex.skills,
                    prerequisites=ex.prerequisites,
                    status=status_of(catalogue, ex.id, passed, opens),
                    pro=ex.id not in free,
                    entitled=paid or ex.id in free,
                )
                for ex in graph.branch_exercises(branch.id)
            ),
        )
        for branch in sorted(graph.branches.values(), key=lambda b: b.order)
    )
    return LearnerMap(
        branches=branches,
        level=level_progress(total_xp(session, user_id)),
        streak=streak_for(session, user_id),
    )


def exercise_view(
    session: Session,
    catalogue: ContentCatalogue,
    user_id: uuid.UUID,
    exercise_id: str,
    *,
    free_per_branch: int,
) -> ExerciseView:
    """The exercise as the learner opens it. A Pro exercise's brief is shown on every plan."""
    exercise = _exercise(catalogue, exercise_id)
    pro = exercise_id not in free_exercises(catalogue.graph, free_per_branch)
    passed = passed_exercises(session, user_id)
    progress = session.get(ExerciseProgress, (user_id, exercise_id))
    draft = session.get(Draft, (user_id, exercise_id))
    attempts = session.scalars(
        select(Attempt)
        .where(Attempt.user_id == user_id, Attempt.exercise_id == exercise_id)
        .order_by(Attempt.created_at.desc())
        .limit(RECENT_ATTEMPTS)
    )
    revealed = progress.hints_revealed if progress else 0
    starter = _starter(exercise)
    files = starter
    source: FilesSource = "starter"
    if draft is not None:
        files = {path: draft.files.get(path, text) for path, text in starter.items()}
        # A reset stores the starter as the draft, so the learner is on the starter again.
        source = "starter" if files == starter else "draft"
    elif carried := _carried_files(session, exercise, user_id):
        files = {**starter, **carried}
        source = "carried"
    return ExerciseView(
        exercise=exercise,
        status=status_of(
            catalogue,
            exercise_id,
            passed,
            learner_unlocks(session, catalogue, user_id, passed, free_per_branch=free_per_branch),
        ),
        hints_revealed=exercise.hints[:revealed],
        files=files,
        files_source=source,
        carried_from=exercise.carry_from if source == "carried" else None,
        recent_attempts=tuple(attempts),
        pro=pro,
        entitled=not pro or is_paid(plans.plan_of(_learner(session, user_id))),
    )


def _starter(exercise: Exercise) -> dict[str, str]:
    return {path: exercise.starter_files[path] for path in exercise.editable}


def _carried_files(session: Session, exercise: Exercise, user_id: uuid.UUID) -> dict[str, str]:
    """The learner's files from their latest passing attempt of `carry_from`, for the paths this
    exercise lets them edit. Empty when there is nothing to carry."""
    if exercise.carry_from is None:
        return {}
    attempt = session.scalars(
        select(Attempt)
        .where(
            Attempt.user_id == user_id,
            Attempt.exercise_id == exercise.carry_from,
            Attempt.status == "passed",
        )
        .order_by(Attempt.created_at.desc())
        .limit(1)
    ).first()
    if attempt is None:
        return {}
    return {path: attempt.files[path] for path in exercise.editable if path in attempt.files}


def reset_to_starter(
    session: Session, catalogue: ContentCatalogue, user_id: uuid.UUID, exercise_id: str
) -> None:
    """Discard the learner's draft and put them back on the starter files.

    The starter is stored as the draft rather than the draft deleted, so carried files do not
    come back the next time the exercise opens."""
    exercise = _exercise(catalogue, exercise_id)
    draft = session.get(Draft, (user_id, exercise_id))
    if draft is None:
        session.add(Draft(user_id=user_id, exercise_id=exercise_id, files=_starter(exercise)))
    else:
        draft.files = _starter(exercise)


def reveal_next_hint(
    session: Session,
    catalogue: ContentCatalogue,
    user_id: uuid.UUID,
    exercise_id: str,
    *,
    free_per_branch: int,
) -> tuple[str, ...]:
    """Reveal one more hint and return every hint revealed so far.

    Hints are part of attempting an exercise, so a Pro exercise's hints need a Pro or Team plan
    (`PlanRequiredError`), checked before prerequisites as for attempts."""
    _exercise(catalogue, exercise_id)
    plans.require_attempt_entitlement(
        _learner(session, user_id), catalogue.graph, exercise_id, free_per_branch
    )
    exercise = _available_exercise(session, catalogue, user_id, exercise_id, free_per_branch)
    progress = progress_for_update(session, user_id, exercise_id)
    if progress.hints_revealed >= len(exercise.hints):
        raise ConflictError("There are no more hints for this exercise.")
    progress.hints_revealed += 1
    return exercise.hints[: progress.hints_revealed]


def save_draft(
    session: Session,
    catalogue: ContentCatalogue,
    user_id: uuid.UUID,
    exercise_id: str,
    files: dict[str, str],
) -> None:
    exercise = _exercise(catalogue, exercise_id)
    _validate_files(exercise, files)
    draft = session.get(Draft, (user_id, exercise_id))
    if draft is None:
        session.add(Draft(user_id=user_id, exercise_id=exercise_id, files=files))
    else:
        draft.files = {**draft.files, **files}


def submit_attempt(
    session: Session,
    catalogue: ContentCatalogue,
    revision_ids: dict[str, int],
    user_id: uuid.UUID,
    exercise_id: str,
    files: dict[str, str],
    *,
    per_minute_limit: int,
    per_day_limit: int | None = None,
    max_queue_depth: int | None = None,
    grading_seconds_per_day: int | None = None,
    free_per_branch: int,
) -> Attempt:
    """Queue an attempt for grading, enforcing the plan, unlocks and abuse limits.

    A Pro exercise needs a Pro or Team plan (`PlanRequiredError`), checked before prerequisites
    because no amount of progress opens it on the free plan.

    A learner has at most one attempt queued or running, across every exercise; at most
    `per_minute_limit` a minute and `per_day_limit` in any 24 hours (attempts the platform could
    not grade do not count), and at most `grading_seconds_per_day` of sandbox time in any 24
    hours, summed from their attempts' recorded durations. With `max_queue_depth` attempts
    already queued, new ones are refused until the workers catch up.

    The attempt is stamped with the learner's local day and a hash of the files here, at
    submission, so later zone changes cannot move it and repeats can be recognised.
    """
    _exercise(catalogue, exercise_id)
    plans.require_attempt_entitlement(
        _learner(session, user_id), catalogue.graph, exercise_id, free_per_branch
    )
    exercise = _available_exercise(session, catalogue, user_id, exercise_id, free_per_branch)
    _validate_files(exercise, files)
    now = datetime.now(UTC)
    in_flight = session.scalar(
        select(Attempt.id).where(
            Attempt.user_id == user_id, Attempt.status.in_(("queued", "running"))
        )
    )
    if in_flight is not None:
        raise _in_flight_conflict()
    if _attempts_since(session, user_id, now - timedelta(minutes=1)) >= per_minute_limit:
        raise RateLimitedError("You are submitting very quickly. Wait a moment and try again.")
    if (
        per_day_limit is not None
        and _attempts_since(session, user_id, now - timedelta(days=1)) >= per_day_limit
    ):
        raise AttemptCapError(
            f"You have used today's {per_day_limit} graded attempts. More become available as "
            "your attempts from 24 hours ago age out.",
            {"limit": per_day_limit},
        )
    if (
        grading_seconds_per_day is not None
        and grading_seconds_since(session, user_id, now - timedelta(days=1))
        >= grading_seconds_per_day
    ):
        minutes = grading_seconds_per_day // 60
        raise GradingBudgetError(
            f"You have used today's {minutes} minutes of grading time. More becomes available "
            "as your runs from 24 hours ago age out.",
            {"budget_minutes": minutes},
        )
    if max_queue_depth is not None:
        queued = session.scalar(
            select(func.count()).select_from(Attempt).where(Attempt.status == "queued")
        )
        if (queued or 0) >= max_queue_depth:
            raise ServiceBusyError(
                "Grading is very busy right now. Your code is saved; try again in a minute."
            )
    attempt = Attempt(
        user_id=user_id,
        exercise_id=exercise_id,
        revision_id=revision_ids[exercise_id],
        files=files,
        files_hash=files_hash(files),
        local_day=local_day(now, learner_zone(session, user_id)),  # stamped, never rewritten
        status="queued",
        created_at=now,
    )
    try:
        with session.begin_nested():
            session.add(attempt)
            session.flush()
    except IntegrityError as err:
        raise _in_flight_conflict() from err
    return attempt


def _in_flight_conflict() -> ConflictError:
    return AttemptInFlightError(
        "You already have an attempt being graded; wait for its result before submitting again."
    )


def _attempts_since(session: Session, user_id: uuid.UUID, since: datetime) -> int:
    count = session.scalar(
        select(func.count())
        .select_from(Attempt)
        .where(Attempt.user_id == user_id, Attempt.created_at > since, Attempt.status != "errored")
    )
    return count or 0


def grading_seconds_since(session: Session, user_id: uuid.UUID, since: datetime) -> float:
    """Sandbox seconds the learner's attempts submitted since `since` took, from each report's
    `duration_ms` (errored attempts included: a run the learner made fail still held a worker)."""
    total_ms = session.scalar(
        select(func.coalesce(func.sum(Attempt.report["duration_ms"].as_integer()), 0)).where(
            Attempt.user_id == user_id,
            Attempt.created_at > since,
            Attempt.report.is_not(None),
        )
    )
    return (total_ms or 0) / 1000


def get_attempt(session: Session, user_id: uuid.UUID, attempt_id: uuid.UUID) -> Attempt:
    attempt = session.get(Attempt, attempt_id)
    if attempt is None or attempt.user_id != user_id:
        raise NotFoundError("No such attempt.")
    return attempt


def _exercise(catalogue: ContentCatalogue, exercise_id: str) -> Exercise:
    source = catalogue.sources.get(exercise_id)
    if source is None:
        raise NotFoundError(f"No exercise called '{exercise_id}'.")
    return source.exercise


def _available_exercise(
    session: Session,
    catalogue: ContentCatalogue,
    user_id: uuid.UUID,
    exercise_id: str,
    free_per_branch: int,
) -> Exercise:
    exercise = _exercise(catalogue, exercise_id)
    passed = passed_exercises(session, user_id)
    opens = learner_unlocks(session, catalogue, user_id, passed, free_per_branch=free_per_branch)
    if status_of(catalogue, exercise_id, passed, opens) == "locked":
        raise ForbiddenError("Complete this exercise's prerequisites first.")
    return exercise


def _validate_files(exercise: Exercise, files: dict[str, str]) -> None:
    try:
        validate_submission(exercise, files)
    except SubmissionError as err:
        raise InvalidInputError(str(err)) from err


def progress_for_update(session: Session, user_id: uuid.UUID, exercise_id: str) -> ExerciseProgress:
    """The learner's progress row, created if missing and locked for the rest of the transaction."""
    session.execute(
        insert(ExerciseProgress)
        .values(user_id=user_id, exercise_id=exercise_id, hints_revealed=0)
        .on_conflict_do_nothing()
    )
    return session.execute(
        select(ExerciseProgress)
        .where(ExerciseProgress.user_id == user_id, ExerciseProgress.exercise_id == exercise_id)
        .with_for_update()
    ).scalar_one()
