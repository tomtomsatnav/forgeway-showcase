"""Plans and entitlements: what a learner's plan lets them attempt.

Being *entitled* to an exercise is separate from it being *available*: availability follows
prerequisites (`PrerequisiteGraph.is_available`), entitlement follows the plan. A learner may
attempt an exercise only when both hold. Briefs stay readable whatever the plan, so a free learner
can see what Pro contains.

The free tier (ADR 0011):

- every exercise in a root branch (one that requires nothing: the foundations);
- the first `free_per_branch` exercises, in the branch's stable order, of every other standard
  branch, never its capstone. Callers pass `LATTICE_FREE_EXERCISES_PER_BRANCH` (the setting
  `free_exercises_per_branch`); there is deliberately no default here, so no path can fall back
  to a different allowance from the rest.

Pro and Team add the rest: capstones, guided projects (`project` branches) and every exercise
past the free allowance, and making certificates public.
"""

from __future__ import annotations

from enum import StrEnum

from lattice.domain.content import BranchKind, PrerequisiteGraph, Tier


class Plan(StrEnum):
    """A learner's plan. Every account starts on `free`; there is no billing yet."""

    FREE = "free"
    PRO = "pro"
    TEAM = "team"


def is_paid(plan: Plan) -> bool:
    """Pro and Team carry every entitlement."""
    return plan is not Plan.FREE


def free_exercises(graph: PrerequisiteGraph, free_per_branch: int) -> frozenset[str]:
    """The exercises the free plan includes. Everything else is Pro."""
    included: set[str] = set()
    for branch in graph.branches.values():
        exercises = graph.branch_exercises(branch.id)
        if branch.kind is BranchKind.PROJECT:
            continue
        if not branch.requires:
            included.update(e.id for e in exercises)
            continue
        included.update(
            e.id for e in exercises[: max(free_per_branch, 0)] if e.tier is not Tier.CAPSTONE
        )
    return frozenset(included)


def is_pro_exercise(graph: PrerequisiteGraph, exercise_id: str, free_per_branch: int) -> bool:
    """True when the exercise is outside the free plan."""
    return exercise_id not in free_exercises(graph, free_per_branch)


def may_attempt(
    plan: Plan,
    graph: PrerequisiteGraph,
    exercise_id: str,
    free_per_branch: int,
) -> bool:
    """Whether the plan entitles the learner to attempt the exercise (prerequisites aside)."""
    return is_paid(plan) or not is_pro_exercise(graph, exercise_id, free_per_branch)


def may_publish_certificates(plan: Plan) -> bool:
    """Making a certificate public is Pro. Certificates are still issued on every plan."""
    return is_paid(plan)
