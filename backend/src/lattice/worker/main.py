"""Grading worker: ``python -m lattice.worker.main``.

Claims queued attempts, grades each in a fresh sandbox and records the result together with
its progression effects. Several workers can run side by side; `SKIP LOCKED` keeps them from
claiming the same attempt, and stale claims from crashed workers are re-queued.
"""

from __future__ import annotations

import logging
import signal
import socket
import time
import uuid
from datetime import timedelta
from types import FrameType

from lattice.application import grading, live_runs, ops
from lattice.domain.grading import SandboxRunner
from lattice.domain.live import LiveSandboxRunner, ModelProvider
from lattice.infrastructure.content_loader import ContentCatalogue, load_catalogue
from lattice.infrastructure.db.engine import get_engine, session_factory, transaction
from lattice.infrastructure.live_anthropic import AnthropicProvider
from lattice.infrastructure.logging_setup import configure
from lattice.infrastructure.sandbox_docker import (
    DockerSandboxConfig,
    DockerSandboxRunner,
    longest_run_s,
)
from lattice.settings import Settings, get_settings

logger = logging.getLogger("lattice.worker")

# How long beyond the longest possible run a claim is still trusted: recording the grade, a slow
# database, a kill that takes a few seconds.
VISIBILITY_MARGIN = timedelta(seconds=60)
MAX_TRIES = 3
STALE_SWEEP_EVERY_S = 30.0
# The heartbeat is written on the poll loop, at most this often, so an idle worker costs one
# small UPDATE every few seconds. A long grading run pauses it (up to `longest_run_s`).
HEARTBEAT_EVERY_S = 5.0


def visibility_timeout(settings: Settings) -> timedelta:
    """How long a claimed attempt may stay running before the sweep takes it back. It must
    outlast the longest run, which grows with `sandbox_timeout_factor` (2 under gVisor in
    production): a shorter one re-queues an attempt that is still being graded, so it is graded
    twice, or errored after `MAX_TRIES`."""
    return timedelta(seconds=longest_run_s(settings.sandbox_timeout_factor)) + VISIBILITY_MARGIN


def live_provider(settings: Settings) -> ModelProvider | None:
    """The platform's model for live runs, holding its key; None while the feature is off."""
    key = settings.live_anthropic_api_key
    if key is None or not key.get_secret_value():
        return None
    return AnthropicProvider(key.get_secret_value(), settings.live_anthropic_base_url)


class Worker:
    def __init__(
        self,
        settings: Settings,
        catalogue: ContentCatalogue,
        runner: SandboxRunner,
        *,
        live_runner: LiveSandboxRunner | None = None,
        provider: ModelProvider | None = None,
    ) -> None:
        self.id = f"{socket.gethostname()}-{uuid.uuid4().hex[:6]}"
        self._sessions = session_factory(get_engine(settings.database_url))
        self._catalogue = catalogue
        self._runner = runner
        self._live_runner = live_runner
        self._provider = provider
        self._live = settings.live_config()
        self._live_visibility = (
            timedelta(seconds=longest_run_s(settings.sandbox_timeout_factor)) + VISIBILITY_MARGIN
        )
        self._poll_s = settings.worker_poll_seconds
        self._free_per_branch = settings.free_exercises_per_branch
        self._visibility_timeout = visibility_timeout(settings)
        self._stopping = False

    def stop(self, signum: int, _frame: FrameType | None) -> None:
        logger.info("stopping after the current attempt", extra={"worker_id": self.id})
        self._stopping = True

    def run_forever(self) -> None:
        logger.info("worker started", extra={"worker_id": self.id})
        last_sweep = 0.0
        last_beat = float("-inf")
        while not self._stopping:
            if time.monotonic() - last_beat >= HEARTBEAT_EVERY_S:
                self.heartbeat()
                last_beat = time.monotonic()
            if time.monotonic() - last_sweep > STALE_SWEEP_EVERY_S:
                self.sweep()
                last_sweep = time.monotonic()
            if not self.run_next():
                time.sleep(self._poll_s)

    def heartbeat(self) -> None:
        with transaction(self._sessions) as session:
            ops.record_heartbeat(session, self.id)

    def sweep(self) -> None:
        with transaction(self._sessions) as session:
            changed = grading.requeue_stale(
                session, visibility_timeout=self._visibility_timeout, max_tries=MAX_TRIES
            )
        if changed:
            logger.warning("recovered stale attempts", extra={"status": changed})
        with transaction(self._sessions) as session:
            lost = live_runs.error_stale(session, visibility_timeout=self._live_visibility)
        if lost:
            logger.warning("gave up on stale live runs", extra={"status": lost})

    def run_next(self) -> bool:
        """Run the oldest queued job of either kind. Returns whether one was processed. If another
        worker takes it first, the other kind still gets its turn."""
        with transaction(self._sessions) as session:
            live_first = self._live_runner is not None and live_runs.next_job_is_live(session)
        if live_first:
            return self.run_live_once() or self.run_once()
        return self.run_once() or self.run_live_once()

    def run_live_once(self) -> bool:
        """Run one live run if any is queued (ADR 0012). Returns whether one was processed."""
        if self._live_runner is None:
            return False
        with transaction(self._sessions) as session:
            claimed = live_runs.claim_next(session, self.id)
        if claimed is None:
            return False
        started = time.monotonic()
        if self._provider is None:
            result = {
                "outcome": "errored",
                "message": "Live runs are switched off on this server.",
                "calls": [],
                "total_cost_usd": 0.0,
            }
        else:
            try:
                result = live_runs.execute(
                    claimed, self._catalogue, self._live_runner, self._provider,
                    self._sessions, self._live,
                )  # fmt: skip
            except Exception:
                # Left running; the sweep errors it. It is never re-run, as it spends money.
                logger.exception("live run crashed", extra={"attempt_id": str(claimed.id)})
                return True
        with transaction(self._sessions) as session:
            live_runs.record_result(session, claimed.id, result)
        logger.info(
            "finished live run",
            extra={
                "attempt_id": str(claimed.id),
                "exercise_id": claimed.exercise_id,
                "status": result["outcome"],
                "duration_ms": int((time.monotonic() - started) * 1000),
            },
        )
        return True

    def run_once(self) -> bool:
        """Grade one attempt if any is queued. Returns whether one was processed."""
        with transaction(self._sessions) as session:
            claimed = grading.claim_next(session, self.id)
        if claimed is None:
            return False
        started = time.monotonic()
        try:
            report = grading.grade(claimed, self._catalogue, self._runner)
        except Exception:
            # Leave the attempt running; the stale sweep retries it or gives up cleanly.
            logger.exception("grading crashed", extra={"attempt_id": str(claimed.id)})
            return True
        with transaction(self._sessions) as session:
            grading.record_grade(
                session,
                self._catalogue,
                claimed.id,
                report,
                free_per_branch=self._free_per_branch,
            )
        logger.info(
            "graded attempt",
            extra={
                "attempt_id": str(claimed.id),
                "exercise_id": claimed.exercise_id,
                "status": report.status.value,
                "duration_ms": int((time.monotonic() - started) * 1000),
            },
        )
        return True


def main() -> None:
    settings = get_settings()
    configure(settings.log_level)
    runner = DockerSandboxRunner(
        DockerSandboxConfig(
            images={"python": settings.sandbox_image_python},
            oci_runtime=settings.sandbox_oci_runtime,
            max_memory_mb=settings.sandbox_max_memory_mb,
            timeout_factor=settings.sandbox_timeout_factor,
        )
    )
    runner.reap_orphans()
    worker = Worker(
        settings,
        load_catalogue(settings.content_dir),
        runner,
        live_runner=runner,
        provider=live_provider(settings),
    )
    signal.signal(signal.SIGTERM, worker.stop)
    signal.signal(signal.SIGINT, worker.stop)
    worker.run_forever()


if __name__ == "__main__":
    main()
