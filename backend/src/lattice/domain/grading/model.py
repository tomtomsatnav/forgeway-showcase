"""Grading value objects and the sandbox port."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from pydantic import BaseModel, ConfigDict


class GradeStatus(StrEnum):
    """`errored` means the platform, not the learner, could not produce a grade."""

    PASSED = "passed"
    FAILED = "failed"
    ERRORED = "errored"


class CheckResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    title: str
    passed: bool
    message: str = ""
    output: str = ""


class GradeReport(BaseModel):
    """The learner-facing outcome of one attempt."""

    model_config = ConfigDict(frozen=True)

    status: GradeStatus
    checks: tuple[CheckResult, ...] = ()
    error: str | None = None
    duration_ms: int = 0

    @property
    def passed(self) -> bool:
        return self.status is GradeStatus.PASSED


@dataclass(frozen=True)
class SandboxRequest:
    """Everything a sandbox needs to grade one submission. Paths are relative POSIX paths."""

    runtime: str
    submission: dict[str, str]
    tests: dict[str, str]
    checks: dict[str, str]  # check id -> pytest node id relative to tests/
    nonce: str
    timeout_s: int
    memory_mb: int
    isolation: str = "inprocess"  # "process" runs learner code in a child interpreter


@dataclass(frozen=True)
class SandboxResult:
    exit_code: int | None
    stdout: str
    stderr: str
    timed_out: bool
    output_truncated: bool
    duration_ms: int


class SandboxRunner(Protocol):
    """Runs untrusted code in isolation. Implementations must enforce the request's limits."""

    def run(self, request: SandboxRequest) -> SandboxResult: ...
