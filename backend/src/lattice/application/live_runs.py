"""In-app live runs (ADR 0012): start and read them in the API, run them in the worker.

A live run executes an exercise's `live.py` over the learner's current files in the grading
sandbox, with every model call relayed to the proxy here: it checks the call, forces the
platform's model, clamps `max_tokens`, enforces the run's limits and the learner's spending
caps, makes the call with the platform's key, and records what it cost. Grades never come from
a live run.
"""

from __future__ import annotations

import json
import logging
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from pydantic import ValidationError
from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from lattice.application import learning, plans, rate_limits
from lattice.application.errors import (
    ConflictError,
    ForbiddenError,
    InvalidInputError,
    LiveCapError,
    LiveRunInFlightError,
    LiveUnavailableError,
    NotFoundError,
    PlanRequiredError,
    RateLimitedError,
    ServiceBusyError,
)
from lattice.domain.entitlements import is_paid
from lattice.domain.grading import SubmissionError
from lattice.domain.grading.service import validate_submission
from lattice.domain.live import (
    MAX_REQUEST_BYTES,
    Allowance,
    LiveCall,
    LiveConfig,
    LiveSandboxRequest,
    LiveSandboxResult,
    LiveSandboxRunner,
    ModelProvider,
    ProviderError,
    RunMeter,
    cost_usd,
    day_start,
    month_start,
)
from lattice.infrastructure.content_loader import ContentCatalogue
from lattice.infrastructure.db.engine import rowcount, transaction
from lattice.infrastructure.db.models import (
    Attempt,
    LiveNoticeAcknowledgement,
    LiveRun,
    Subscription,
    User,
)
from lattice.infrastructure.db.models import LiveCall as LiveCallRow

logger = logging.getLogger(__name__)

LIVE_SCRIPT = "live.py"
LIVE_NEEDS_PRO = (
    "Live runs on Forgeway's model are part of Forgeway Pro, which is not open yet. Run locally "
    "with your own key meanwhile, or join the waitlist to hear when Pro opens."
)
NO_LIVE_EXAMPLE = (
    "This exercise has no live example yet. Use Run locally to call your code against a real "
    "model with your own key."
)


# The data notice a learner acknowledges before their first live run (UK GDPR transparency,
# docs/legal/compliance-review-2026-11.md, "Live runs and AI"). Change the wording, change the
# version: every learner is asked again.
LIVE_NOTICE_VERSION = "2026-11-03"
LIVE_NOTICE = (
    "A live run sends your current files and the messages your program sends to Anthropic, PBC "
    "in the United States, which runs the model as Forgeway's processor. Anthropic does not "
    "train its models on them, and deletes them within 30 days (up to 2 years only if its "
    "safety systems flag them). Forgeway keeps each run's files and output for 30 days, and its "
    "usage records (tokens and cost) for 13 months. Nothing from a live run is used for grading."
)
RUN_RETENTION = timedelta(days=30)
# A run queued this long is given up on: the learner has one in flight at a time.
QUEUED_TOO_LONG = timedelta(minutes=10)
USAGE_RETENTION_MONTHS = 13


class LiveNoticeRequiredError(ConflictError):
    """The learner has not acknowledged the current live-run data notice."""

    code = "live-notice-required"


class NoLiveExampleError(ConflictError):
    """The exercise has no `live.py`, so there is nothing to run live."""

    code = "no-live-example"


def has_live_example(catalogue: ContentCatalogue, exercise_id: str) -> bool:
    source = catalogue.sources.get(exercise_id)
    return source is not None and (source.root / LIVE_SCRIPT).is_file()


# Spending ---------------------------------------------------------------------------------------


def allowance(
    session: Session, user: User, config: LiveConfig, now: datetime | None = None
) -> Allowance:
    """The learner's live-run caps and what they have spent this UTC month and day."""
    now = now or datetime.now(UTC)
    plan = plans.plan_of(user)
    sub = session.get(Subscription, user.id)

    def spent_since(since: datetime) -> float:
        total = session.scalar(
            select(func.coalesce(func.sum(LiveCallRow.cost_usd), 0)).where(
                LiveCallRow.user_id == user.id, LiveCallRow.created_at >= since
            )
        )
        return float(total or 0)

    interval = sub.interval if sub is not None else None
    daily_cap = config.policy.daily_cap(plan, interval)
    if is_paid(plan) and sub is not None and sub.status == "trialing" and sub.started_at:
        # One allowance for the whole trial, however many UTC months it touches.
        return Allowance(
            monthly_cap_usd=config.policy.trial_usd,
            spent_month_usd=spent_since(sub.started_at),
            daily_cap_usd=min(daily_cap, config.policy.trial_usd),
            spent_today_usd=spent_since(day_start(now)),
            now=now,
            trial_end=sub.trial_end,
        )
    return Allowance(
        monthly_cap_usd=config.policy.monthly_cap(plan, interval),
        spent_month_usd=spent_since(month_start(now)),
        daily_cap_usd=daily_cap,
        spent_today_usd=spent_since(day_start(now)),
        now=now,
    )


def cap_message(current: Allowance) -> str:
    """What the learner reads at a cap: which one, and when it resets. Never silent."""
    when = current.resets_at.strftime("%-d %B %Y at %H:%M UTC")
    if current.exhausted == "month" and current.trial_end is not None:
        return (
            f"You have used your trial's live-run allowance (${current.monthly_cap_usd:.2f}). "
            f"Pro's full allowance starts when the trial ends on {when}. Your checks are "
            "unaffected, and Run locally still works with your own key."
        )
    if current.exhausted == "month":
        return (
            f"You have used this month's live-run allowance (${current.monthly_cap_usd:.2f}). "
            f"It resets on {when}. Your checks are unaffected, and Run locally still works with "
            "your own key."
        )
    return (
        f"You have used today's share of your live-run allowance (${current.daily_cap_usd:.2f}). "
        f"More becomes available on {when}. Your checks are unaffected."
    )


def _require_allowance(current: Allowance) -> None:
    if current.exhausted is not None:
        trial = current.exhausted == "month" and current.trial_end is not None
        raise LiveCapError(
            cap_message(current),
            {
                "scope": "trial" if trial else current.exhausted,
                "resets_at": current.resets_at.isoformat(),
            },
        )


def live_seconds_since(session: Session, user_id: uuid.UUID, since: datetime) -> float:
    """Seconds the learner's runs held the worker, from claim to finish, for runs finished since
    `since` (errored ones included: they held it too)."""
    total = session.scalar(
        select(func.sum(func.extract("epoch", LiveRun.finished_at - LiveRun.claimed_at))).where(
            LiveRun.user_id == user_id, LiveRun.finished_at > since
        )
    )
    return float(total or 0)


def _require_live_time(session: Session, user_id: uuid.UUID, config: LiveConfig) -> None:
    """The daily time budget, so one learner's slow programs cannot hold the single worker. Kept
    apart from `grading_seconds_per_day`: live time must never use up a learner's checks."""
    now = datetime.now(UTC)
    since = now - timedelta(days=1)
    if live_seconds_since(session, user_id, since) < config.seconds_per_day:
        return
    oldest = session.scalar(
        select(func.min(LiveRun.finished_at)).where(
            LiveRun.user_id == user_id, LiveRun.finished_at > since
        )
    )
    resets_at = (oldest or now) + timedelta(days=1)
    raise LiveCapError(
        f"Your live runs have used today's {config.seconds_per_day // 60} minutes of run time. "
        f"More becomes available on {resets_at.strftime('%-d %B %Y at %H:%M UTC')}. Your checks "
        "are unaffected, and Run locally still works with your own key.",
        {"scope": "time", "resets_at": resets_at.isoformat()},
    )


# The data notice ---------------------------------------------------------------------------------


def notice_acknowledged(session: Session, user_id: uuid.UUID) -> bool:
    return (
        session.scalar(
            select(LiveNoticeAcknowledgement.id).where(
                LiveNoticeAcknowledgement.user_id == user_id,
                LiveNoticeAcknowledgement.version == LIVE_NOTICE_VERSION,
            )
        )
        is not None
    )


def acknowledge_notice(session: Session, user_id: uuid.UUID, version: str) -> None:
    """Record that the learner acknowledged the notice, once per wording. Only the current
    wording can be acknowledged, so the record always names text the learner was shown."""
    if version != LIVE_NOTICE_VERSION:
        raise InvalidInputError("That notice has changed; read the current one and try again.")
    # Two tabs acknowledging together: the second insert does nothing rather than fail.
    session.execute(
        insert(LiveNoticeAcknowledgement)
        .values(user_id=user_id, version=version)
        .on_conflict_do_nothing(constraint="uq_live_notice_once_per_version")
    )


# Retention --------------------------------------------------------------------------------------


@dataclass(frozen=True)
class LivePurgeSummary:
    runs: int
    calls: int


def purge_expired(session: Session, now: datetime | None = None) -> LivePurgeSummary:
    """Delete live runs (their files and output) after 30 days, and usage records after 13
    months. A deleted run's usage rows keep their numbers (`run_id` becomes null). Idempotent."""
    now = now or datetime.now(UTC)
    runs = rowcount(
        session.execute(
            delete(LiveRun).where(
                LiveRun.created_at < now - RUN_RETENTION,
                LiveRun.status.in_(("finished", "errored")),
            )
        )
    )
    months_back = now.year * 12 + now.month - 1 - USAGE_RETENTION_MONTHS
    year, month = divmod(months_back, 12)
    usage_cutoff = now.replace(year=year, month=month + 1, day=min(now.day, 28))
    calls = rowcount(
        session.execute(delete(LiveCallRow).where(LiveCallRow.created_at < usage_cutoff))
    )
    return LivePurgeSummary(int(runs), int(calls))


# The API's side ---------------------------------------------------------------------------------


def start_live_run(
    session: Session,
    catalogue: ContentCatalogue,
    user_id: uuid.UUID,
    exercise_id: str,
    files: dict[str, str],
    *,
    config: LiveConfig,
    free_per_branch: int,
    max_queue_depth: int,
) -> LiveRun:
    """Queue a live run of the learner's `files` with the exercise's `live.py`.

    Entitlement is judged as the exercise view judges it (a Pro exercise needs a paid plan), and
    the exercise must be open to the learner, as for attempts: a guided-project milestone's
    starter is the previous reference solution, and a live program could print it. Then the
    learner's plan must carry a live-run allowance with some left this month and day, there is
    one live run in flight per learner, an hourly cap, and a queue-depth limit.
    """
    if not config.enabled:
        raise LiveUnavailableError("Live runs are switched off on this server.")
    view = learning.exercise_view(
        session, catalogue, user_id, exercise_id, free_per_branch=free_per_branch
    )
    if not view.entitled:
        raise PlanRequiredError(plans.ATTEMPT_NEEDS_PRO)
    if view.status == "locked":
        raise ForbiddenError("Complete this exercise's prerequisites first.")
    if not has_live_example(catalogue, exercise_id):
        raise NoLiveExampleError(NO_LIVE_EXAMPLE)
    if not notice_acknowledged(session, user_id):
        raise LiveNoticeRequiredError(
            "Before your first live run, read and acknowledge where its data goes."
        )
    try:
        validate_submission(view.exercise, files)
    except SubmissionError as err:
        raise InvalidInputError(str(err)) from err
    user = session.get(User, user_id)
    if user is None:
        raise NotFoundError("No such learner.")
    current = allowance(session, user, config)
    if current.monthly_cap_usd <= 0:
        raise PlanRequiredError(LIVE_NEEDS_PRO)
    _require_allowance(current)
    _require_live_time(session, user_id, config)
    in_flight = session.scalar(
        select(LiveRun.id).where(
            LiveRun.user_id == user_id, LiveRun.status.in_(("queued", "running"))
        )
    )
    if in_flight is not None:
        raise _in_flight()
    if not rate_limits.consume(
        session, f"live:user:{user_id}", limit=config.runs_per_hour, window=timedelta(hours=1)
    ):
        raise RateLimitedError(
            f"You have started {config.runs_per_hour} live runs in the last hour. Wait a little "
            "and try again."
        )
    queued = session.scalar(
        select(func.count()).select_from(LiveRun).where(LiveRun.status == "queued")
    )
    if (queued or 0) >= max_queue_depth:
        raise ServiceBusyError("Live runs are very busy right now. Try again in a minute.")
    run = LiveRun(user_id=user_id, exercise_id=exercise_id, files=files, status="queued")
    try:
        with session.begin_nested():
            session.add(run)
            session.flush()
    except IntegrityError as err:
        raise _in_flight() from err
    return run


def _in_flight() -> LiveRunInFlightError:
    return LiveRunInFlightError("You already have a live run going; wait for it to finish.")


def get_live_run(session: Session, user_id: uuid.UUID, run_id: uuid.UUID) -> LiveRun:
    run = session.get(LiveRun, run_id)
    if run is None or run.user_id != user_id:
        raise NotFoundError("No such live run.")
    return run


# The worker's side ------------------------------------------------------------------------------


@dataclass(frozen=True)
class ClaimedLiveRun:
    id: uuid.UUID
    user_id: uuid.UUID
    exercise_id: str
    files: dict[str, str]


def next_job_is_live(session: Session) -> bool:
    """Whether the oldest queued job is a live run rather than an attempt, so neither kind
    starves the other on a single worker."""
    live = session.scalar(select(func.min(LiveRun.created_at)).where(LiveRun.status == "queued"))
    attempt = session.scalar(select(func.min(Attempt.created_at)).where(Attempt.status == "queued"))
    return live is not None and (attempt is None or live < attempt)


def claim_next(session: Session, worker_id: str) -> ClaimedLiveRun | None:
    """Claim the oldest queued live run; concurrent workers never claim the same row."""
    run = session.scalars(
        select(LiveRun)
        .where(LiveRun.status == "queued")
        .order_by(LiveRun.created_at)
        .limit(1)
        .with_for_update(skip_locked=True)
    ).first()
    if run is None:
        return None
    run.status = "running"
    run.worker_id = worker_id
    run.claimed_at = datetime.now(UTC)
    return ClaimedLiveRun(run.id, run.user_id, run.exercise_id, dict(run.files))


def error_stale(session: Session, *, visibility_timeout: timedelta) -> int:
    """Live runs a dead worker held become `errored`, with the calls they made and what those
    cost. They are never re-run: a run spends money, and those calls are already recorded. Runs
    left queued past `QUEUED_TOO_LONG` become `errored` too, so the learner is not locked out by
    their own in-flight run."""
    now = datetime.now(UTC)
    runs = session.scalars(
        select(LiveRun)
        .where(LiveRun.status == "running", LiveRun.claimed_at < now - visibility_timeout)
        .with_for_update(skip_locked=True)
    ).all()
    for run in runs:
        calls = _recorded_calls(session, run.id)
        run.status = "errored"
        run.finished_at = now
        run.result = _result(
            "errored", "The live run could not complete. Only the calls it made were counted."
        ) | {"calls": calls, "total_cost_usd": round(sum(c["cost_usd"] for c in calls), 8)}
    waited_out = rowcount(
        session.execute(
            update(LiveRun)
            .where(LiveRun.status == "queued", LiveRun.created_at < now - QUEUED_TOO_LONG)
            .values(
                status="errored",
                finished_at=now,
                result=_result(
                    "errored",
                    "Live runs were too busy to start yours, so it was dropped. Nothing was "
                    "spent; try again.",
                ),
            )
        )
    )
    return len(runs) + int(waited_out)


def _recorded_calls(session: Session, run_id: uuid.UUID) -> list[dict[str, Any]]:
    """A run's calls as `LiveProxy` reports them, from the rows it recorded them in."""
    rows = session.scalars(
        select(LiveCallRow).where(LiveCallRow.run_id == run_id).order_by(LiveCallRow.id)
    )
    return [
        {
            "model": row.model,
            "input_tokens": row.input_tokens,
            "output_tokens": row.output_tokens,
            "cache_read_tokens": row.cache_read_tokens,
            "cache_write_tokens": row.cache_write_tokens,
            "cost_usd": float(row.cost_usd),
            "latency_ms": row.latency_ms,
            "outcome": row.outcome,
        }
        for row in rows
    ]


class LiveProxy:
    """The host side of the live channel: one learner's run, one call at a time.

    Every request from the sandbox is hostile input: it is size-checked and validated against
    `LiveCall`, which names every field that may reach the provider. Then the run's limits and
    the learner's caps are checked, the call is made on the platform's model with `max_tokens`
    clamped, and its cost is recorded in its own transaction before the reply goes back.
    """

    def __init__(
        self,
        claimed: ClaimedLiveRun,
        sessions: sessionmaker[Session],
        provider: ModelProvider,
        config: LiveConfig,
    ) -> None:
        self.claimed = claimed
        self.sessions = sessions
        self.provider = provider
        self.config = config
        self.meter = RunMeter(config.limits)

    def __call__(self, body: Any, *, timeout_s: float | None = None) -> dict[str, Any]:
        try:
            size = len(json.dumps(body))
        except (TypeError, ValueError):
            return _refuse("invalid", "the request could not be read")
        if size > MAX_REQUEST_BYTES:
            return _refuse(
                "invalid",
                f"the request is {size:,} bytes; a live call may send at most "
                f"{MAX_REQUEST_BYTES:,} (about 100K tokens)",
            )
        try:
            call = LiveCall.model_validate(body)
        except ValidationError as err:
            first = err.errors()[0]
            where = ".".join(str(p) for p in first["loc"])
            return _refuse("invalid", f"the request is not one the live proxy accepts: {where}: "
                           f"{first['msg']}")  # fmt: skip
        if refusal := self.meter.refusal():
            return _refuse("limit", refusal)
        with transaction(self.sessions) as session:
            user = session.get(User, self.claimed.user_id)
            if user is None:
                return _refuse("limit", "this account no longer exists")
            current = allowance(session, user, self.config)
        if current.exhausted is not None:
            return _refuse("limit", cap_message(current))
        limits = self.config.limits
        max_tokens = max(
            min(limits.max_output_tokens_per_call, limits.max_tokens - self.meter.tokens), 1
        )
        self.meter.calls += 1
        record: dict[str, Any] = {
            "model": self.config.model,
            "requested_model": call.model or None,
            "max_tokens": min(call.max_tokens, max_tokens),
        }
        try:
            reply = self.provider.complete(
                call, model=self.config.model, max_tokens=max_tokens, timeout_s=timeout_s
            )
        except ProviderError as err:
            self._record(record, outcome=err.kind)
            return {
                "error": {
                    "kind": err.kind,
                    "message": err.message,
                    "retry_after_s": err.retry_after_s,
                }
            }
        usage = reply.usage
        cost = cost_usd(usage, self.config.rate)
        self.meter.tokens += usage.input_tokens + usage.output_tokens
        record.update(
            model=reply.model,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cache_read_tokens=usage.cache_read_tokens,
            cache_write_tokens=usage.cache_write_tokens,
            cost_usd=round(cost, 8),
            latency_ms=reply.latency_ms,
        )
        self._record(record, outcome="ok")
        return {"completion": reply.completion}

    def _record(self, record: dict[str, Any], *, outcome: str) -> None:
        record.setdefault("input_tokens", 0)
        record.setdefault("output_tokens", 0)
        record.setdefault("cache_read_tokens", 0)
        record.setdefault("cache_write_tokens", 0)
        record.setdefault("cost_usd", 0.0)
        record.setdefault("latency_ms", 0)
        record["outcome"] = outcome
        self.meter.records.append(record)
        with transaction(self.sessions) as session:
            session.add(
                LiveCallRow(
                    user_id=self.claimed.user_id,
                    run_id=self.claimed.id,
                    exercise_id=self.claimed.exercise_id,
                    model=str(record["model"])[:64],
                    input_tokens=record["input_tokens"],
                    output_tokens=record["output_tokens"],
                    cache_read_tokens=record["cache_read_tokens"],
                    cache_write_tokens=record["cache_write_tokens"],
                    cost_usd=Decimal(str(record["cost_usd"])),
                    latency_ms=record["latency_ms"],
                    outcome=outcome,
                )
            )


def _refuse(kind: str, message: str) -> dict[str, Any]:
    return {"error": {"kind": kind, "message": message}}


def execute(
    claimed: ClaimedLiveRun,
    catalogue: ContentCatalogue,
    runner: LiveSandboxRunner,
    provider: ModelProvider,
    sessions: sessionmaker[Session],
    config: LiveConfig,
) -> dict[str, Any]:
    """Run the live run in the sandbox and return its result for `record_result`."""
    source = catalogue.sources.get(claimed.exercise_id)
    if source is None:
        return _result("errored", "This exercise is no longer available.")
    script = source.root / LIVE_SCRIPT
    if not script.is_file():
        return _result("no-live-example", NO_LIVE_EXAMPLE)
    exercise = source.exercise
    files = {**exercise.starter_files, **claimed.files, LIVE_SCRIPT: script.read_text("utf-8")}
    proxy = LiveProxy(claimed, sessions, provider, config)
    request = LiveSandboxRequest(
        runtime=exercise.runtime,
        files=files,
        nonce=secrets.token_hex(16),
        timeout_s=config.limits.timeout_s,
        memory_mb=exercise.limits.memory_mb,
        max_output_bytes=config.limits.max_output_bytes,
    )
    outcome = runner.run_live(request, proxy)
    if outcome.container_stderr.strip():
        logger.info("live sandbox stderr: %s", outcome.container_stderr[-2000:])
    return summarise(outcome, proxy.meter.records, config)


def summarise(
    outcome: LiveSandboxResult, calls: list[dict[str, Any]], config: LiveConfig
) -> dict[str, Any]:
    """The learner-facing result of a run: what the program printed, and what each call cost."""
    if outcome.error == "no-live-script":
        kind, message = "no-live-example", NO_LIVE_EXAMPLE
    elif outcome.timed_out:
        kind = "timed-out"
        message = (
            f"Your program ran past the {config.limits.timeout_s} seconds a live run may take, "
            "so it was stopped."
        )
    elif outcome.error in ("bad-message", "protocol"):
        kind = "stopped"
        message = (
            "Your program wrote something to the live channel that is not a model call, so the "
            "run was stopped. Call the model only through the client forgeway_kit gives you."
        )
    elif outcome.error is not None:
        kind = "errored"
        message = "The live run could not complete. Only the calls it made were counted."
    elif outcome.exit_status not in (0, None):
        kind = "finished"
        message = f"Your program exited with status {outcome.exit_status}; see its output."
    else:
        kind, message = "finished", None
    result = _result(kind, message)
    result.update(
        exit_status=outcome.exit_status,
        stdout=outcome.stdout,
        stderr=outcome.stderr,
        stdout_truncated=outcome.stdout_truncated,
        stderr_truncated=outcome.stderr_truncated,
        duration_ms=outcome.duration_ms,
        calls=calls,
        total_cost_usd=round(sum(float(c["cost_usd"]) for c in calls), 8),
    )
    return result


def _result(kind: str, message: str | None) -> dict[str, Any]:
    return {"outcome": kind, "message": message, "calls": [], "total_cost_usd": 0.0}


def record_result(session: Session, run_id: uuid.UUID, result: dict[str, Any]) -> None:
    """Store the result. A run no longer running (the sweep gave up on it) is left as it is."""
    run = session.get(LiveRun, run_id, with_for_update=True)
    if run is None or run.status != "running":
        return
    run.status = "errored" if result["outcome"] == "errored" else "finished"
    run.result = result
    run.finished_at = datetime.now(UTC)
