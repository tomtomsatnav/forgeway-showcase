"""Per-IP, per-email and per-account limits, counted in Postgres (`application.rate_limits`).

Each check commits in its own transaction, so a hit still counts when the request it guards
fails afterwards (a wrong password, say) and its own transaction rolls back.
"""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy.orm import Session, sessionmaker

from lattice.application import rate_limits
from lattice.application.errors import RateLimitedError
from lattice.infrastructure.db.engine import transaction


class RateLimiter:
    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self._sessions = sessions

    def check(self, key: str, *, limit: int, window: timedelta, message: str) -> None:
        """Count a hit for `key`, or raise `RateLimitedError` with `message` if over `limit`."""
        with transaction(self._sessions) as session:
            allowed = rate_limits.consume(session, key, limit=limit, window=window)
        if not allowed:
            raise RateLimitedError(message)
