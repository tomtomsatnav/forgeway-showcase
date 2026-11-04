"""Forgeway Pro: the waitlist. There is no billing and no email is sent (ADR 0011)."""

from __future__ import annotations

from fastapi import APIRouter

from lattice.api import schemas
from lattice.api.deps import CurrentLearner, Db, MutatingLearner
from lattice.api.schemas import PROBLEM_RESPONSES
from lattice.application import plans
from lattice.infrastructure.db.models import ProWaitlistEntry

router = APIRouter(prefix="/api/pro", tags=["pro"], responses=PROBLEM_RESPONSES)


def _status(entry: ProWaitlistEntry | None) -> schemas.WaitlistStatus:
    if entry is None:
        return schemas.WaitlistStatus(joined=False, plan_interest=None, joined_at=None)
    interest: plans.PlanInterest = "team" if entry.plan_interest == "team" else "pro"
    return schemas.WaitlistStatus(joined=True, plan_interest=interest, joined_at=entry.joined_at)


@router.get("/waitlist")
def waitlist_status(learner: CurrentLearner, db: Db) -> schemas.WaitlistStatus:
    """Whether the learner has joined the Pro waitlist."""
    return _status(plans.waitlist_entry(db, learner.user.id))


@router.post("/waitlist")
def join_waitlist(
    body: schemas.WaitlistJoin, learner: MutatingLearner, db: Db
) -> schemas.WaitlistStatus:
    """Join the waitlist. Idempotent: one entry per learner, keeping when they first joined.

    Records the learner's email, the plan they are interested in and the time. Nothing is
    charged and no email is sent."""
    return _status(plans.join_waitlist(db, learner.user, body.plan))
