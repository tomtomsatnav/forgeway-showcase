"""XP rewards genuine progress: it is earned once per exercise, by passing it.

Nothing is awarded for logging in, viewing pages or resubmitting passed work. The only bonus
is for solving an exercise without revealing its hints, a signal of real understanding.
Revealing a hint never takes away the base award.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from lattice.domain.content import Exercise

NO_HINT_BONUS_RATE = 0.2


class XpReason(StrEnum):
    PASSED = "passed"
    NO_HINTS = "no-hints"


@dataclass(frozen=True)
class XpAward:
    reason: XpReason
    amount: int


def awards_for_pass(
    exercise: Exercise, *, hints_revealed: int, previously_passed: bool
) -> list[XpAward]:
    """XP earned by a passing attempt. Empty if the learner had already passed the exercise."""
    if previously_passed:
        return []
    awards = [XpAward(XpReason.PASSED, exercise.xp)]
    if exercise.hints and hints_revealed == 0:
        awards.append(XpAward(XpReason.NO_HINTS, round(exercise.xp * NO_HINT_BONUS_RATE)))
    return awards
