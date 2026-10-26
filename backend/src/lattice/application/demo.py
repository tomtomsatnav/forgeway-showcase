"""Seed a demo learner with partial progress, for local exploration and screenshots."""

from __future__ import annotations

import uuid
from contextlib import suppress
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from lattice.application import accounts, certificates, progression
from lattice.application.errors import ForbiddenError
from lattice.application.streak import files_hash
from lattice.domain.grading import CheckResult, GradeReport, GradeStatus
from lattice.domain.progression import GENERAL, awards_for_pass, local_day
from lattice.infrastructure.content_loader import ContentCatalogue
from lattice.infrastructure.db.models import Attempt, ExerciseProgress, User, XpEvent

DEMO_EMAIL = "demo@forgeway.dev"
DEMO_PASSWORD = "forgeway-demo-password"  # noqa: S105 - public, local-only demo account
DEMO_ALLOCATIONS = 3
PASSES_PER_DAY = 1  # the showcase seeds the 10 foundations only; keeps a week-plus streak


def seed_demo_learner(
    session: Session,
    catalogue: ContentCatalogue,
    revision_ids: dict[str, int],
    passed: int,
    *,
    free_per_branch: int,
) -> bool:
    """Create the demo learner having passed the first `passed` exercises with their reference
    solutions, spread over the last few days so the streak is live. Once the foundations are
    done the learner takes the retrieval path and a few talents. Returns False if the learner
    already exists."""
    if session.scalar(select(User.id).where(User.email == DEMO_EMAIL)) is not None:
        return False
    user = accounts.register(
        session, email=DEMO_EMAIL, password=DEMO_PASSWORD, display_name="Demo learner"
    )
    user.email_verified_at = datetime.now(UTC)  # a local demo: no inbox to verify
    # Only exercises with a reference solution: a showcase copy has them for the foundations only.
    ids = [i for i in catalogue.graph.order if catalogue.sources[i].solution()][:passed]
    for index, exercise_id in enumerate(ids):
        source = catalogue.sources[exercise_id]
        exercise = source.exercise
        report = GradeReport(
            status=GradeStatus.PASSED,
            checks=tuple(CheckResult(id=c.id, title=c.title, passed=True) for c in exercise.checks),
        )
        now = datetime.now(UTC) - timedelta(days=(len(ids) - 1 - index) // PASSES_PER_DAY)
        attempt = Attempt(
            user_id=user.id,
            exercise_id=exercise_id,
            revision_id=revision_ids[exercise_id],
            files=source.solution(),
            files_hash=files_hash(source.solution()),
            local_day=local_day(now, UTC),
            status="passed",
            created_at=now,
            report=report.model_dump(mode="json"),
            finished_at=now,
        )
        session.add(attempt)
        session.flush()
        session.add(
            ExerciseProgress(
                user_id=user.id,
                exercise_id=exercise_id,
                hints_revealed=0,
                first_passed_at=now,
                passing_attempt_id=attempt.id,
            )
        )
        for award in awards_for_pass(exercise, hints_revealed=0, previously_passed=False):
            session.add(
                XpEvent(
                    user_id=user.id,
                    exercise_id=exercise_id,
                    reason=award.reason.value,
                    amount=award.amount,
                    attempt_id=attempt.id,
                )
            )
        session.flush()
        progression.evaluate_badges(session, catalogue, user.id, attempt.id)
        for issued in certificates.issue_certificates(
            session, catalogue, user.id, [exercise.branch], attempt.id
        ):  # the demo's certificates are public, so there is a verification page to see
            certificates.update_certificate(session, user.id, issued.id, is_public=True)
    _take_path_and_talents(session, catalogue, user.id, free_per_branch)
    return True


def _take_path_and_talents(
    session: Session, catalogue: ContentCatalogue, user_id: uuid.UUID, free_per_branch: int
) -> None:
    specialisations = list(catalogue.progression.tree.paths)
    if not specialisations:
        return
    with suppress(ForbiddenError):  # foundations unfinished: stay a generalist
        progression.set_path(
            session, catalogue, user_id, specialisations[0], free_per_branch=free_per_branch
        )
    for _ in range(DEMO_ALLOCATIONS):
        view = progression.talent_tree_view(session, catalogue, user_id)
        # Prefer the specialisation's own talents, so the demo shows the path at work.
        available = sorted(
            (n.node for n in view.nodes if n.status.state == "available"),
            key=lambda node: node.subtree == GENERAL,
        )
        if not available:
            return
        progression.allocate_talent(session, catalogue, user_id, available[0].id)
