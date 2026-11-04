"""Streaks count learning days, not visits. Everything here is date arithmetic.

A learning day is a local calendar date on which the learner had at least one graded attempt
that counted. Each attempt is stamped with its date in the learner's time zone when it is
submitted (`local_day`), so changing the zone later never rewrites history. The current streak
is the run of consecutive learning days that ends today or yesterday in the learner's current
zone; skipping a whole day ends it. There is no freeze mechanic.
"""

from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass
from datetime import date, datetime, timedelta, tzinfo


@dataclass(frozen=True)
class Streak:
    current: int
    longest: int


def local_day(instant: datetime, zone: tzinfo) -> date:
    """The calendar date of `instant` in `zone`."""
    if instant.tzinfo is None:
        raise ValueError("instant must be timezone-aware")
    return instant.astimezone(zone).date()


def current_streak(days: Collection[date], today: date) -> int:
    """Consecutive learning days ending today or yesterday; 0 if the last one is older."""
    day = today if today in days else today - timedelta(days=1)
    count = 0
    while day in days:
        count += 1
        day -= timedelta(days=1)
    return count


def longest_streak(days: Collection[date]) -> int:
    """The longest run of consecutive learning days ever."""
    longest = run = 0
    previous: date | None = None
    for day in sorted(set(days)):
        run = run + 1 if previous is not None and day - previous == timedelta(days=1) else 1
        longest = max(longest, run)
        previous = day
    return longest


def streak_of(days: Collection[date], today: date) -> Streak:
    return Streak(current_streak(days, today), longest_streak(days))
