"""Worker-side use cases: claim queued attempts, grade them and apply progression."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from lattice.application.certificates import issue_certificates
from lattice.application.learning import (
    learner_unlocks,
    passed_exercises,
    progress_for_update,
    total_xp,
)
from lattice.application.progression import evaluate_badges
from lattice.application.streak import GRADED, streak_for
from lattice.domain.grading import GradeReport, GradeStatus, SandboxRunner, grade_submission
from lattice.domain.progression import awards_for_pass, level_progress, talent_points
from lattice.infrastructure.content_loader import ContentCatalogue
from lattice.infrastructure.db.engine import rowcount
from lattice.infrastructure.db.models import Attempt, XpEvent


@dataclass(frozen=True)
class ClaimedAttempt:
    id: uuid.UUID
    user_id: uuid.UUID
    exercise_id: str
    files: dict[str, str]


def claim_next(session: Session, worker_id: str) -> ClaimedAttempt | None:
    """Claim the oldest queued attempt. Concurrent workers never claim the same row."""
    attempt = session.scalars(
        select(Attempt)
        .where(Attempt.status == "queued")
        .order_by(Attempt.created_at)
        .limit(1)
        .with_for_update(skip_locked=True)
    ).first()
    if attempt is None:
        return None
    attempt.status = "running"
    attempt.worker_id = worker_id
    attempt.claimed_at = datetime.now(UTC)
    attempt.tries += 1
    return ClaimedAttempt(attempt.id, attempt.user_id, attempt.exercise_id, dict(attempt.files))


def requeue_stale(session: Session, *, visibility_timeout: timedelta, max_tries: int) -> int:
    """Return attempts held by dead workers to the queue, or error them after `max_tries`."""
    cutoff = datetime.now(UTC) - visibility_timeout
    stale = Attempt.status == "running", Attempt.claimed_at < cutoff
    errored = GradeReport(
        status=GradeStatus.ERRORED,
        error="Grading could not complete after several tries. This attempt does not count "
        "against you.",
    )
    gave_up = rowcount(
        session.execute(
            update(Attempt)
            .where(*stale, Attempt.tries >= max_tries)
            .values(
                status="errored",
                report=errored.model_dump(mode="json"),
                finished_at=datetime.now(UTC),
            )
        )
    )
    requeued = rowcount(
        session.execute(
            update(Attempt).where(*stale, Attempt.tries < max_tries).values(status="queued")
        )
    )
    return int(gave_up) + int(requeued)


def grade(
    claimed: ClaimedAttempt, catalogue: ContentCatalogue, runner: SandboxRunner
) -> GradeReport:
    """Run the sandbox. Content that has since disappeared yields an errored report."""
    source = catalogue.sources.get(claimed.exercise_id)
    if source is None:
        return GradeReport(
            status=GradeStatus.ERRORED, error="This exercise is no longer available."
        )
    tests = source.tests()
    if not tests:  # a showcase copy without this exercise's hidden tests (content_loader)
        return GradeReport(
            status=GradeStatus.ERRORED,
            error="This showcase copy does not include the hidden tests for this exercise, so it "
            "cannot be graded here. Only the foundations grade locally; the full course is at "
            "https://forgeway.dev.",
        )
    return grade_submission(source.exercise, tests, claimed.files, runner)


def record_grade(
    session: Session,
    catalogue: ContentCatalogue,
    attempt_id: uuid.UUID,
    report: GradeReport,
    *,
    free_per_branch: int,
) -> None:
    """Store the report and apply its progression effects in the caller's transaction.

    Idempotent: a report for an attempt that is no longer running is ignored, XP has a unique
    key per learner, exercise and reason, and badges are unique per learner, so none can be
    awarded twice. Badges and the streak are evaluated for every graded attempt, passed or
    failed; errored attempts earn and count for nothing.
    """
    attempt = session.get(Attempt, attempt_id, with_for_update=True)
    if attempt is None or attempt.status != "running":
        return
    payload = report.model_dump(mode="json")
    attempt.status = report.status.value
    attempt.finished_at = datetime.now(UTC)
    if report.status.value in GRADED:
        progression = (
            _apply_pass(session, catalogue, attempt, free_per_branch) if report.passed else None
        )
        payload["progression"] = _finish_graded(session, catalogue, attempt, progression)
    attempt.report = payload


def _finish_graded(
    session: Session,
    catalogue: ContentCatalogue,
    attempt: Attempt,
    progression: dict[str, Any] | None,
) -> dict[str, Any]:
    """Award badges and certificates and add them, talent points gained and the streak."""
    user_id = attempt.user_id
    if progression is None:  # a failed attempt moves no XP
        level = level_progress(total_xp(session, user_id)).level
        progression = {
            "xp_awarded": 0,
            "awards": [],
            "level_before": level,
            "level_after": level,
            "unlocked": [],
        }
    session.flush()  # the queries below must see this attempt's graded status and its XP
    badges = evaluate_badges(session, catalogue, user_id, attempt.id)
    certificates = []
    if attempt.status == GradeStatus.PASSED.value:  # only a pass can complete a branch
        branch = catalogue.sources[attempt.exercise_id].exercise.branch
        certificates = issue_certificates(session, catalogue, user_id, [branch], attempt.id)
    streak = streak_for(session, user_id)
    gained = talent_points(progression["level_after"]) - talent_points(progression["level_before"])
    return {
        **progression,
        "badges_awarded": [
            {"id": b.id, "title": b.title, "description": b.description} for b in badges
        ],
        "certificates_issued": [
            {
                "id": c.id,
                "branch_id": c.branch_id,
                "branch_title": c.branch_title,
                "includes_capstone": c.includes_capstone,
            }
            for c in certificates
        ],
        "talent_points_gained": gained,
        "streak": {"current": streak.current, "longest": streak.longest},
    }


def _apply_pass(
    session: Session, catalogue: ContentCatalogue, attempt: Attempt, free_per_branch: int
) -> dict[str, Any]:
    user_id, exercise_id = attempt.user_id, attempt.exercise_id
    progress = progress_for_update(session, user_id, exercise_id)
    passed_before = passed_exercises(session, user_id)
    xp_before = total_xp(session, user_id)

    awards = awards_for_pass(
        catalogue.sources[exercise_id].exercise,
        hints_revealed=progress.hints_revealed,
        previously_passed=progress.first_passed_at is not None,
    )
    awarded = 0
    for award in awards:
        inserted = rowcount(
            session.execute(
                insert(XpEvent)
                .values(
                    user_id=user_id,
                    exercise_id=exercise_id,
                    reason=award.reason.value,
                    amount=award.amount,
                    attempt_id=attempt.id,
                )
                .on_conflict_do_nothing(constraint="uq_xp_once_per_reason")
            )
        )
        awarded += award.amount if inserted else 0
    if progress.first_passed_at is None:
        progress.first_passed_at = datetime.now(UTC)
        progress.passing_attempt_id = attempt.id

    passed_after = passed_before | {exercise_id}
    before = learner_unlocks(
        session, catalogue, user_id, passed_before, free_per_branch=free_per_branch
    )
    after = learner_unlocks(
        session, catalogue, user_id, passed_after, free_per_branch=free_per_branch
    )
    return {
        "xp_awarded": awarded,
        "awards": [{"reason": a.reason.value, "amount": a.amount} for a in awards],
        "level_before": level_progress(xp_before).level,
        "level_after": level_progress(xp_before + awarded).level,
        "unlocked": list(after.newly_unlocked(before)),
    }
