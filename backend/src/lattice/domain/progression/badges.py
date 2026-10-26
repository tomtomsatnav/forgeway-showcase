"""Badges: content-defined awards with criteria from a closed set.

Badges are evaluated against a snapshot of the learner's facts after every graded attempt, so
they can be earned by failing as well as passing (a streak, for instance). They are never
revoked, which is why `streak_days` looks at the longest streak rather than the current one.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from lattice.domain.content.model import Slug

_Count = Annotated[int, Field(ge=1, le=10_000)]


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


@dataclass(frozen=True)
class LearnerFacts:
    """What the criteria are judged against."""

    completed_branches: frozenset[str]
    exercises_passed: int
    first_try_passes: int  # exercises whose first graded attempt passed
    no_hint_passes: int  # exercises passed without revealing a hint (those that have hints)
    longest_streak: int
    level: int
    capstones_passed: int  # capstone exercises passed


class BranchComplete(_Frozen):
    kind: Literal["branch_complete"]
    branch: Slug

    def met(self, facts: LearnerFacts) -> bool:
        return self.branch in facts.completed_branches

    def describe(self, branch_titles: Mapping[str, str]) -> str:
        return f"Pass every exercise in {branch_titles.get(self.branch, self.branch)}."


class ExercisesPassed(_Frozen):
    kind: Literal["exercises_passed"]
    n: _Count

    def met(self, facts: LearnerFacts) -> bool:
        return facts.exercises_passed >= self.n

    def describe(self, branch_titles: Mapping[str, str]) -> str:
        return f"Pass {self.n} {'exercise' if self.n == 1 else 'exercises'}."


class FirstTry(_Frozen):
    kind: Literal["first_try"]
    n: _Count

    def met(self, facts: LearnerFacts) -> bool:
        return facts.first_try_passes >= self.n

    def describe(self, branch_titles: Mapping[str, str]) -> str:
        noun = "exercise" if self.n == 1 else "exercises"
        return f"Pass {self.n} {noun} on your first graded attempt."


class NoHintPasses(_Frozen):
    kind: Literal["no_hint_passes"]
    n: _Count

    def met(self, facts: LearnerFacts) -> bool:
        return facts.no_hint_passes >= self.n

    def describe(self, branch_titles: Mapping[str, str]) -> str:
        noun = "exercise" if self.n == 1 else "exercises"
        return f"Pass {self.n} {noun} without revealing a hint."


class StreakDays(_Frozen):
    kind: Literal["streak_days"]
    n: _Count

    def met(self, facts: LearnerFacts) -> bool:
        return facts.longest_streak >= self.n

    def describe(self, branch_titles: Mapping[str, str]) -> str:
        return f"Learn on {self.n} days in a row."


class LevelReached(_Frozen):
    kind: Literal["level_reached"]
    n: _Count

    def met(self, facts: LearnerFacts) -> bool:
        return facts.level >= self.n

    def describe(self, branch_titles: Mapping[str, str]) -> str:
        return f"Reach level {self.n}."


class CapstonesPassed(_Frozen):
    kind: Literal["capstones_passed"]
    n: _Count

    def met(self, facts: LearnerFacts) -> bool:
        return facts.capstones_passed >= self.n

    def describe(self, branch_titles: Mapping[str, str]) -> str:
        return f"Pass {self.n} {'capstone project' if self.n == 1 else 'capstone projects'}."


Criterion = Annotated[
    BranchComplete
    | ExercisesPassed
    | FirstTry
    | NoHintPasses
    | StreakDays
    | LevelReached
    | CapstonesPassed,
    Field(discriminator="kind"),
]


class Badge(_Frozen):
    id: Slug
    title: Annotated[str, StringConstraints(min_length=1, max_length=60)]
    description: Annotated[str, StringConstraints(min_length=1, max_length=200)]
    criterion: Criterion


def badge_problems(badges: Iterable[Badge], *, branches: Iterable[str]) -> list[str]:
    """Every problem with a badge set: duplicate ids and branches that do not exist."""
    known = set(branches)
    problems: list[str] = []
    seen: set[str] = set()
    for badge in badges:
        if badge.id in seen:
            problems.append(f"badge '{badge.id}' is defined more than once")
        seen.add(badge.id)
        if isinstance(badge.criterion, BranchComplete) and badge.criterion.branch not in known:
            problems.append(
                f"badge '{badge.id}' refers to unknown branch '{badge.criterion.branch}'"
            )
    return problems


def newly_earned(
    facts: LearnerFacts, already_awarded: Iterable[str], badges: Iterable[Badge]
) -> list[Badge]:
    """Badges whose criteria are met and that have not been awarded yet, in definition order."""
    awarded = set(already_awarded)
    return [b for b in badges if b.id not in awarded and b.criterion.met(facts)]
