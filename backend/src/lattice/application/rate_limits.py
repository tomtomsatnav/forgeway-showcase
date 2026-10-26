"""Sliding-window rate limits kept in Postgres, so they hold across restarts and API processes."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select, text
from sqlalchemy.orm import Session

from lattice.infrastructure.db.engine import rowcount
from lattice.infrastructure.db.models import RateLimitHit

# Longer than any window in use, so pruning never forgets a hit that still counts.
RETAIN = timedelta(days=1)


def consume(
    session: Session, key: str, *, limit: int, window: timedelta, now: datetime | None = None
) -> bool:
    """Record a hit for `key` and return True, or return False if `limit` hits already fall in
    the trailing `window` (a refused request is not counted).

    Hits for one key are serialised with a transaction-scoped advisory lock, so concurrent
    requests cannot both take the last slot.
    """
    now = now or datetime.now(UTC)
    session.execute(text("SELECT pg_advisory_xact_lock(hashtext(:key))"), {"key": key})
    since = now - window
    session.execute(delete(RateLimitHit).where(RateLimitHit.key == key, RateLimitHit.at <= since))
    used = session.scalar(
        select(func.count()).select_from(RateLimitHit).where(RateLimitHit.key == key)
    )
    if (used or 0) >= limit:
        return False
    session.add(RateLimitHit(key=key, at=now))
    return True


def prune(session: Session, now: datetime | None = None) -> int:
    """Delete hits too old to count for any limit. Returns how many went."""
    cutoff = (now or datetime.now(UTC)) - RETAIN
    return rowcount(session.execute(delete(RateLimitHit).where(RateLimitHit.at < cutoff)))
