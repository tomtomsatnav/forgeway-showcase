"""Operations status for the host's health check: worker liveness and grading queue age.

It carries no secrets or personal data, but it is not for the public either: Caddy answers
404 for /api/ops/ and the health check calls the site on 127.0.0.1 directly.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from lattice.api.deps import State
from lattice.application import ops

# Kept out of the OpenAPI schema: it is for the host, not the SPA.
router = APIRouter(prefix="/api/ops", tags=["ops"], include_in_schema=False)


class WorkerStatus(BaseModel):
    last_seen_at: datetime | None
    age_s: float | None
    seen_last_5m: int


class QueueStatus(BaseModel):
    queued: int
    running: int
    oldest_queued_age_s: float | None


class OpsStatusOut(BaseModel):
    worker: WorkerStatus
    queue: QueueStatus


@router.get("/status", response_model=OpsStatusOut, responses={503: {}})
def ops_status(state: State) -> OpsStatusOut | JSONResponse:
    """When a worker last polled the queue, and how many attempts wait and for how long."""
    try:
        with state.sessions() as session:
            current = ops.status(session)
    except Exception:
        return JSONResponse({"status": "database unavailable"}, status_code=503)
    return OpsStatusOut(
        worker=WorkerStatus(
            last_seen_at=current.worker_last_seen_at,
            age_s=current.worker_age_s,
            seen_last_5m=current.workers_seen_last_5m,
        ),
        queue=QueueStatus(
            queued=current.queued,
            running=current.running,
            oldest_queued_age_s=current.oldest_queued_age_s,
        ),
    )
