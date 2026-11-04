"""A claimed attempt is only taken back once no run could still be going (M4 of the review)."""

from __future__ import annotations

from datetime import timedelta

import pytest

from lattice.domain.grading import SandboxRequest
from lattice.infrastructure.sandbox_docker import (
    MAX_RUN_S,
    DockerSandboxConfig,
    DockerSandboxRunner,
    longest_run_s,
)
from lattice.settings import Settings
from lattice.worker.main import VISIBILITY_MARGIN, visibility_timeout


def request(timeout_s: int) -> SandboxRequest:
    return SandboxRequest(
        runtime="python",
        submission={},
        tests={},
        checks={},
        nonce="n",
        timeout_s=timeout_s,
        memory_mb=256,
    )


@pytest.mark.parametrize("factor", [1.0, 2.0, 5.0])
def test_the_visibility_timeout_outlasts_the_longest_deadline_the_runner_allows(factor: float):
    runner = DockerSandboxRunner(DockerSandboxConfig(images={}, timeout_factor=factor))
    longest_deadline = timedelta(seconds=runner.deadline_s(request(MAX_RUN_S)))
    timeout = visibility_timeout(Settings(sandbox_timeout_factor=factor))
    assert timeout >= longest_deadline + VISIBILITY_MARGIN
    assert timeout == timedelta(seconds=longest_run_s(factor)) + VISIBILITY_MARGIN


def test_production_under_gvisor_waits_well_past_three_minutes():
    # LATTICE_SANDBOX_TIMEOUT_FACTOR=2: a 120 s exercise may run 250 s with start-up.
    timeout = visibility_timeout(Settings(sandbox_timeout_factor=2))
    assert timeout == timedelta(seconds=310)
    assert timeout > timedelta(minutes=3)
