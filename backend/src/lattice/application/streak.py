"""Learning days, time zones and the files hash that keeps junk resubmissions from counting."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, date, datetime
from functools import cache
from zoneinfo import ZoneInfo, available_timezones

from sqlalchemy import and_, exists, or_, select
from sqlalchemy.orm import Session, aliased

from lattice.application.errors import InvalidInputError
from lattice.domain.progression import Streak, local_day, streak_of
from lattice.infrastructure.db.models import Attempt, LearnerProfile

GRADED = ("passed", "failed")  # errored attempts never count


@cache
def _known_zones() -> frozenset[str]:
    return frozenset(available_timezones())


def validate_time_zone(name: str) -> ZoneInfo:
    """The zone for an IANA name, or `InvalidInputError` if `zoneinfo` does not know it."""
    if name not in _known_zones():
        raise InvalidInputError(f"'{name}' is not a time zone we recognise.")
    return ZoneInfo(name)


def learner_zone(session: Session, user_id: uuid.UUID) -> ZoneInfo:
    profile = session.get(LearnerProfile, user_id)
    return ZoneInfo(profile.time_zone if profile else "UTC")


def files_hash(files: dict[str, str]) -> str:
    """SHA-256 of the canonical submission: sorted paths, UTF-8, no incidental formatting."""
    canonical = json.dumps(files, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode()).hexdigest()


def learning_days(session: Session, user_id: uuid.UUID) -> frozenset[date]:
    """Local days with at least one graded attempt that was not a repeat of earlier work.

    An attempt is a repeat when an earlier graded attempt on the same exercise by the same
    learner has an identical files hash. Attempts that predate hashing (null) are never repeats.
    """
    earlier = aliased(Attempt)
    repeat = exists().where(
        earlier.user_id == Attempt.user_id,
        earlier.exercise_id == Attempt.exercise_id,
        earlier.files_hash == Attempt.files_hash,
        earlier.status.in_(GRADED),
        or_(
            earlier.created_at < Attempt.created_at,
            and_(earlier.created_at == Attempt.created_at, earlier.id < Attempt.id),
        ),
    )
    rows = session.scalars(
        select(Attempt.local_day)
        .where(Attempt.user_id == user_id, Attempt.status.in_(GRADED), ~repeat)
        .distinct()
    )
    return frozenset(rows)


def streak_for(session: Session, user_id: uuid.UUID, *, now: datetime | None = None) -> Streak:
    """Current and longest streak, with "today" taken in the learner's current zone."""
    today = local_day(now or datetime.now(UTC), learner_zone(session, user_id))
    return streak_of(learning_days(session, user_id), today)
