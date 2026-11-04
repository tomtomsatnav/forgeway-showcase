"""In-app live runs (ADR 0012): start one, poll it, and read the learner's allowance."""

from __future__ import annotations

import uuid
from datetime import timedelta

from fastapi import APIRouter, status

from lattice.api import schemas
from lattice.api.deps import CurrentLearner, Db, MutatingLearner, State, VerifiedLearner
from lattice.api.schemas import PROBLEM_RESPONSES
from lattice.application import live_runs
from lattice.domain.live import Allowance
from lattice.infrastructure.db.models import LiveRun

router = APIRouter(prefix="/api", tags=["live"], responses=PROBLEM_RESPONSES)
NOTICE_ACKNOWLEDGEMENTS_PER_HOUR = 30  # per account: well past any tab left retrying


@router.post("/exercises/{exercise_id}/live-runs", status_code=status.HTTP_202_ACCEPTED)
def start_live_run(
    exercise_id: str, body: schemas.FilesBody, learner: VerifiedLearner, db: Db, state: State
) -> schemas.LiveRunDetail:
    """Run the learner's files with the exercise's `live.py` against Forgeway's model, paid for
    by the platform. Poll the returned run for its output. Grades never come from a live run.

    Needs a verified email (403 `email-unverified`); a Pro exercise needs a paid plan, and live
    runs need a plan with an allowance (403 `plan-required`); the exercise must be open to the
    learner (403) and have a live example (409 `no-live-example`), and the learner must have
    acknowledged the current data notice (409 `live-notice-required`). At the monthly, daily or
    trial spending cap, or the daily run-time budget, 429 `live-cap` with `scope` ("month", "day",
    "trial" or "time") and `resets_at`. One live run at a time (409
    `live-run-in-flight`), an hourly cap (429 `rate-limited`), a full queue (503 `busy`), and
    503 `live-unavailable` where the server has no platform key.
    """
    config = state.settings.live_config()
    run = live_runs.start_live_run(
        db,
        state.catalogue,
        learner.user.id,
        exercise_id,
        body.files,
        config=config,
        free_per_branch=state.settings.free_exercises_per_branch,
        max_queue_depth=state.settings.max_queue_depth,
    )
    return _detail(run, live_runs.allowance(db, learner.user, config))


@router.get("/live-runs/{run_id}")
def get_live_run(
    run_id: uuid.UUID, learner: CurrentLearner, db: Db, state: State
) -> schemas.LiveRunDetail:
    run = live_runs.get_live_run(db, learner.user.id, run_id)
    return _detail(run, live_runs.allowance(db, learner.user, state.settings.live_config()))


@router.get("/live/notice")
def live_notice(learner: CurrentLearner, db: Db) -> schemas.LiveNotice:
    """The data notice a learner acknowledges before their first live run, and whether they
    have acknowledged this wording."""
    return schemas.LiveNotice(
        version=live_runs.LIVE_NOTICE_VERSION,
        text=live_runs.LIVE_NOTICE,
        acknowledged=live_runs.notice_acknowledged(db, learner.user.id),
    )


@router.post("/live/notice")
def acknowledge_live_notice(
    body: schemas.LiveNoticeAcknowledgement, learner: MutatingLearner, db: Db, state: State
) -> schemas.LiveNotice:
    """Record that the learner acknowledged the notice (who, when, which wording). A stale
    version answers 422."""
    state.limiter.check(
        f"live-notice:user:{learner.user.id}",
        limit=NOTICE_ACKNOWLEDGEMENTS_PER_HOUR,
        window=timedelta(hours=1),
        message="Too many tries. Try again later.",
    )
    live_runs.acknowledge_notice(db, learner.user.id, body.version)
    return schemas.LiveNotice(
        version=live_runs.LIVE_NOTICE_VERSION, text=live_runs.LIVE_NOTICE, acknowledged=True
    )


@router.get("/live/allowance")
def live_allowance(learner: CurrentLearner, db: Db, state: State) -> schemas.LiveAllowance:
    """The learner's live-run allowance and spending this UTC month and day."""
    return _allowance(live_runs.allowance(db, learner.user, state.settings.live_config()))


def _allowance(current: Allowance) -> schemas.LiveAllowance:
    return schemas.LiveAllowance(
        monthly_cap_usd=round(current.monthly_cap_usd, 6),
        spent_month_usd=round(current.spent_month_usd, 6),
        daily_cap_usd=round(current.daily_cap_usd, 6),
        spent_today_usd=round(current.spent_today_usd, 6),
        remaining_usd=round(current.remaining_usd, 6),
        exhausted=current.exhausted,
        resets_at=current.resets_at,
    )


def _detail(run: LiveRun, current: Allowance) -> schemas.LiveRunDetail:
    result = run.result or {}
    return schemas.LiveRunDetail(
        id=run.id,
        exercise_id=run.exercise_id,
        status=run.status,
        created_at=run.created_at,
        finished_at=run.finished_at,
        outcome=result.get("outcome"),
        message=result.get("message"),
        exit_status=result.get("exit_status"),
        stdout=result.get("stdout", ""),
        stderr=result.get("stderr", ""),
        stdout_truncated=result.get("stdout_truncated", False),
        stderr_truncated=result.get("stderr_truncated", False),
        duration_ms=result.get("duration_ms"),
        calls=[schemas.LiveCallSummary(**c) for c in result.get("calls", [])],
        total_cost_usd=result.get("total_cost_usd", 0.0),
        allowance=_allowance(current),
    )
