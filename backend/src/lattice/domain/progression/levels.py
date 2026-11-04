"""The level curve. Each level needs a little more XP than the last.

Reaching level n needs ``100 * (n - 1) ** 1.5`` XP in total, so early levels come quickly
(level 2 at 100 XP, level 5 at 800) and later ones reflect sustained work (level 20 at ~8,300).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

MAX_LEVEL = 60


def xp_threshold(level: int) -> int:
    """Total XP needed to reach `level`."""
    if not 1 <= level <= MAX_LEVEL:
        raise ValueError(f"level must be between 1 and {MAX_LEVEL}")
    return round(100 * math.pow(level - 1, 1.5))


@dataclass(frozen=True)
class LevelProgress:
    level: int
    total_xp: int
    level_floor: int  # total XP at which the current level began
    next_level_at: int | None  # total XP for the next level; None at the cap

    @property
    def fraction(self) -> float:
        """Progress through the current level, from 0.0 to 1.0."""
        if self.next_level_at is None:
            return 1.0
        return (self.total_xp - self.level_floor) / (self.next_level_at - self.level_floor)


def level_progress(total_xp: int) -> LevelProgress:
    """The level reached with `total_xp` and progress towards the next."""
    if total_xp < 0:
        raise ValueError("total XP cannot be negative")
    estimate = min(MAX_LEVEL, 1 + math.floor((total_xp / 100) ** (2 / 3)))
    # Correct floating-point drift at exact boundaries.
    while estimate < MAX_LEVEL and xp_threshold(estimate + 1) <= total_xp:
        estimate += 1
    while xp_threshold(estimate) > total_xp:
        estimate -= 1
    next_at = xp_threshold(estimate + 1) if estimate < MAX_LEVEL else None
    return LevelProgress(estimate, total_xp, xp_threshold(estimate), next_at)
