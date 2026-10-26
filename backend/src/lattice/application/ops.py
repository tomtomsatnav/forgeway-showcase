"""Operational signals: worker heartbeats and the state of the grading queue.

Nothing here is secret or personal: counts, ages and timestamps only, so the status can be
served to the host's health check.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from lattice.infrastructure.db.models import Attempt, WorkerHeartbeat

FORGET_SILENT_WORKERS_AFTER = timedelta(days=1)


@dataclass(frozen=True)
class OpsStatus:
    worker_last_seen_at: datetime | None
    worker_age_s: float | None  # seconds since any worker last polled; None if none ever has
    workers_seen_last_5m: int
    queued: int
    running: int
    oldest_queued_age_s: float | None


def record_heartbeat(session: Session, worker_id: str, now: datetime | None = None) -> None:
    """Mark a worker as alive now, and forget workers silent for a day."""
    now = now or datetime.now(UTC)
    statement = insert(WorkerHeartbeat).values(
        worker_id=worker_id, started_at=now, last_seen_at=now
    )
    session.execute(
        statement.on_conflict_do_update(
            index_elements=[WorkerHeartbeat.worker_id], set_={"last_seen_at": now}
        )
    )
    session.execute(
        delete(WorkerHeartbeat).where(
            WorkerHeartbeat.last_seen_at < now - FORGET_SILENT_WORKERS_AFTER
        )
    )


def status(session: Session, now: datetime | None = None) -> OpsStatus:
    now = now or datetime.now(UTC)
    last_seen = session.scalar(select(func.max(WorkerHeartbeat.last_seen_at)))
    recent = session.scalar(
        select(func.count()).where(WorkerHeartbeat.last_seen_at >= now - timedelta(minutes=5))
    )
    queued, running, oldest = session.execute(
        select(
            func.count().filter(Attempt.status == "queued"),
            func.count().filter(Attempt.status == "running"),
            func.min(Attempt.created_at).filter(Attempt.status == "queued"),
        ).where(Attempt.status.in_(("queued", "running")))
    ).one()
    return OpsStatus(
        worker_last_seen_at=last_seen,
        worker_age_s=_age(now, last_seen),
        workers_seen_last_5m=int(recent or 0),
        queued=int(queued),
        running=int(running),
        oldest_queued_age_s=_age(now, oldest),
    )


def _age(now: datetime, then: datetime | None) -> float | None:
    return None if then is None else round(max((now - then).total_seconds(), 0.0), 1)
