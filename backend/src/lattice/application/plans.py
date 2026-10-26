"""Plans and the Pro waitlist: enforcing entitlements, setting a plan, joining and exporting.

There is no billing (ADR 0011): the owner sets a plan by hand, and the waitlist only records who
asked. No email is sent from here.
"""

from __future__ import annotations

import csv
import io
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from lattice.application.accounts import normalise_email
from lattice.application.errors import InvalidInputError, NotFoundError, PlanRequiredError
from lattice.domain.content import PrerequisiteGraph
from lattice.domain.entitlements import (
    Plan,
    free_exercises,
    is_paid,
    may_attempt,
    may_publish_certificates,
)
from lattice.infrastructure.db.models import ProWaitlistEntry, User

PlanInterest = Literal["pro", "team"]

ATTEMPT_NEEDS_PRO = (
    "This exercise is part of Forgeway Pro, which is not open yet. You can read the brief now; "
    "join the waitlist to hear when Pro opens."
)
PUBLISH_NEEDS_PRO = (
    "Making a certificate public is part of Forgeway Pro, which is not open yet. Join the "
    "waitlist to hear when Pro opens."
)


def plan_of(user: User) -> Plan:
    return Plan(user.plan)


@dataclass(frozen=True)
class Unlocks:
    """What a learner on a plan may open, judged on their passed exercises (ADR 0011).

    A paid learner has everything open: no prerequisite holds back an exercise or a branch, so
    an upgrade never leaves anything waiting on a capstone (owner's decision, 2026-10-26). A free
    learner unlocks the exercises their plan includes on every *free* exercise passed: Pro
    exercises, which the plan cannot attempt, count as done. So a branch that requires a
    non-root branch (Knowledge graphs requires Retrieval, capstone included) opens on the free
    plan once the required branch's free exercises are passed, rather than never. Pro exercises
    are judged on the passed set alone, so nothing behind the plan looks open. Whether an
    exercise is *passed* is always the learner's own record, never this.
    """

    graph: PrerequisiteGraph
    passed: frozenset[str]
    free: frozenset[str]
    paid: bool

    @property
    def _counted(self) -> frozenset[str]:
        return self.passed | (frozenset(self.graph.exercises) - self.free)

    def is_available(self, exercise_id: str) -> bool:
        if self.paid:
            return exercise_id in self.graph.exercises
        included = exercise_id in self.free
        return self.graph.is_available(exercise_id, self._counted if included else self.passed)

    def is_branch_unlocked(self, branch_id: str) -> bool:
        if self.paid:
            return True
        included = any(e.id in self.free for e in self.graph.branch_exercises(branch_id))
        return self.graph.is_branch_unlocked(branch_id, self._counted if included else self.passed)

    def newly_unlocked(self, before: Unlocks) -> tuple[str, ...]:
        """Exercises available now that were not under `before` (fewer passed, same plan)."""
        return tuple(
            i
            for i in self.graph.order
            if i not in self.passed and self.is_available(i) and not before.is_available(i)
        )


def unlocks(
    plan: Plan,
    graph: PrerequisiteGraph,
    passed: frozenset[str],
    free_per_branch: int,
) -> Unlocks:
    return Unlocks(graph, passed, free_exercises(graph, free_per_branch), is_paid(plan))


def require_attempt_entitlement(
    user: User, graph: PrerequisiteGraph, exercise_id: str, free_per_branch: int
) -> None:
    """Raise `PlanRequiredError` unless the learner's plan lets them attempt the exercise."""
    if not may_attempt(plan_of(user), graph, exercise_id, free_per_branch):
        raise PlanRequiredError(ATTEMPT_NEEDS_PRO)


def require_publish_entitlement(user: User) -> None:
    if not may_publish_certificates(plan_of(user)):
        raise PlanRequiredError(PUBLISH_NEEDS_PRO)


def set_plan(session: Session, email: str, plan: Plan) -> User:
    """Put the account with this email on `plan`. The owner's tool; there is no billing."""
    user = session.scalars(select(User).where(User.email == normalise_email(email))).first()
    if user is None:
        raise NotFoundError(f"No account with the email '{email}'.")
    user.plan = plan.value
    return user


def join_waitlist(session: Session, user: User, interest: PlanInterest) -> ProWaitlistEntry:
    """Add the learner to the waitlist. Idempotent: one row per learner, keeping the first
    `joined_at`; joining again updates the plan of interest and the email address."""
    if interest not in ("pro", "team"):
        raise InvalidInputError("The plan of interest must be 'pro' or 'team'.")
    return session.scalars(
        insert(ProWaitlistEntry)
        .values(
            user_id=user.id, email=user.email, plan_interest=interest, joined_at=datetime.now(UTC)
        )
        .on_conflict_do_update(
            index_elements=[ProWaitlistEntry.user_id],
            set_={"plan_interest": interest, "email": user.email},
        )
        .returning(ProWaitlistEntry),
        execution_options={"populate_existing": True},
    ).one()


def waitlist_entry(session: Session, user_id: uuid.UUID) -> ProWaitlistEntry | None:
    return session.get(ProWaitlistEntry, user_id)


def export_waitlist_csv(session: Session) -> str:
    """Every waitlist entry, oldest first, as CSV with a header row."""
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(["email", "plan_interest", "joined_at"])
    for entry in session.scalars(
        select(ProWaitlistEntry).order_by(ProWaitlistEntry.joined_at, ProWaitlistEntry.email)
    ):
        writer.writerow([_cell(entry.email), entry.plan_interest, entry.joined_at.isoformat()])
    return out.getvalue()


def _cell(value: str) -> str:
    """Neutralise a value a spreadsheet would read as a formula."""
    return f"'{value}" if value[:1] in ("=", "+", "-", "@") else value
