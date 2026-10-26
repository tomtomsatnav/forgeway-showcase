"""Grade a submission: assemble the sandbox request, run it and interpret the report."""

from __future__ import annotations

import json
import secrets
from collections.abc import Mapping

from lattice.domain.content import Exercise
from lattice.domain.grading.model import (
    CheckResult,
    GradeReport,
    GradeStatus,
    SandboxRequest,
    SandboxResult,
    SandboxRunner,
)

REPORT_PREFIX = "LATTICE-REPORT"
MAX_FILE_BYTES = 64 * 1024


class SubmissionError(ValueError):
    """The submission itself is unacceptable (wrong paths, too large)."""


def grade_submission(
    exercise: Exercise,
    tests: Mapping[str, str],
    files: Mapping[str, str],
    runner: SandboxRunner,
) -> GradeReport:
    """Grade `files` (the learner's editable files) against the exercise's checks."""
    validate_submission(exercise, files)
    nonce = secrets.token_hex(16)
    request = SandboxRequest(
        runtime=exercise.runtime,
        submission={**exercise.starter_files, **files},
        tests=dict(tests),
        checks={c.id: c.test for c in exercise.checks},
        nonce=nonce,
        timeout_s=exercise.limits.timeout_s,
        memory_mb=exercise.limits.memory_mb,
        isolation=exercise.isolation.value,
    )
    return interpret(exercise, runner.run(request), nonce)


def validate_submission(exercise: Exercise, files: Mapping[str, str]) -> None:
    """Only declared editable files may be submitted, each within the size cap."""
    unexpected = sorted(set(files) - set(exercise.editable))
    if unexpected:
        raise SubmissionError(f"these files cannot be edited in this exercise: {unexpected}")
    for path, text in files.items():
        if len(text.encode()) > MAX_FILE_BYTES:
            raise SubmissionError(f"'{path}' is larger than {MAX_FILE_BYTES // 1024} KB")


def interpret(exercise: Exercise, result: SandboxResult, nonce: str) -> GradeReport:
    """Turn raw sandbox output into a grade, rejecting anything inconsistent."""
    if result.timed_out:
        return _learner_failure(
            exercise,
            f"Your code took longer than {exercise.limits.timeout_s} seconds. "
            "Look for an infinite loop or work that grows faster than expected.",
            result.duration_ms,
        )
    if result.output_truncated:
        return _learner_failure(
            exercise,
            "Your code wrote too much output. Remove debugging prints inside loops.",
            result.duration_ms,
        )
    lines = [ln for ln in result.stdout.splitlines() if ln.startswith(f"{REPORT_PREFIX} {nonce} ")]
    if len(lines) != 1:
        if result.exit_code == 137:
            return _learner_failure(
                exercise,
                f"Your code used more than {exercise.limits.memory_mb} MB of memory.",
                result.duration_ms,
            )
        return _errored("no single valid report was produced", result)
    try:
        payload = json.loads(lines[0].split(" ", 2)[2])
        outcomes = {c["id"]: c for c in payload["checks"]}
        exit_status = int(payload["exit_status"])
    except (ValueError, KeyError, TypeError):
        return _errored("the report could not be parsed", result)

    if set(outcomes) != {c.id for c in exercise.checks}:
        return _errored("the report's checks do not match the exercise", result)
    checks = tuple(
        CheckResult(
            id=c.id,
            title=c.title,
            passed=outcomes[c.id]["outcome"] == "passed",
            message=str(outcomes[c.id].get("message", "")),
            output=str(outcomes[c.id].get("output", "")),
        )
        for c in exercise.checks
    )
    all_passed = all(c.passed for c in checks)
    # pytest exits 0 only when every selected test passed; disagreement means tampering or a bug.
    if all_passed != (exit_status == 0):
        return _errored("the report disagrees with the test run's exit status", result)
    return GradeReport(
        status=GradeStatus.PASSED if all_passed else GradeStatus.FAILED,
        checks=checks,
        duration_ms=result.duration_ms,
    )


def _learner_failure(exercise: Exercise, message: str, duration_ms: int) -> GradeReport:
    return GradeReport(
        status=GradeStatus.FAILED,
        checks=tuple(
            CheckResult(id=c.id, title=c.title, passed=False, message=message)
            for c in exercise.checks
        ),
        duration_ms=duration_ms,
    )


def _errored(reason: str, result: SandboxResult) -> GradeReport:
    return GradeReport(
        status=GradeStatus.ERRORED,
        error=f"Grading could not complete: {reason}. This attempt does not count against you.",
        duration_ms=result.duration_ms,
    )
