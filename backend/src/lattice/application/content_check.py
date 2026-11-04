"""Prove every exercise is solvable and fails usefully, by grading it for real."""

from __future__ import annotations

import time
from dataclasses import dataclass

from lattice.domain.content import GradingAssets
from lattice.domain.grading import GradeStatus, SandboxRunner, grade_submission

# A reference solution should grade in under this many seconds in a local Docker sandbox: the
# production sandbox (gVisor, one CPU) is about four times slower (docs/authoring.md).
SOLUTION_BUDGET_S = 15.0


@dataclass(frozen=True)
class CaseResult:
    exercise_id: str
    case: str  # "solution" or the wrong case's name
    ok: bool
    detail: str
    seconds: float = 0.0  # wall-clock time to grade the case


def check_exercise(source: GradingAssets, runner: SandboxRunner) -> list[CaseResult]:
    """Grade the reference solution (must pass) and each wrong case (must fail as declared)."""
    exercise = source.exercise
    tests = source.tests()
    results: list[CaseResult] = []

    started = time.perf_counter()
    report = grade_submission(exercise, tests, source.solution(), runner)
    seconds = time.perf_counter() - started
    failing = [f"{c.id}: {c.message}" for c in report.checks if not c.passed]
    results.append(
        CaseResult(
            exercise.id,
            "solution",
            report.status is GradeStatus.PASSED,
            report.error or "; ".join(failing) or "passed",
            seconds,
        )
    )

    for case in source.wrong_cases():
        started = time.perf_counter()
        report = grade_submission(exercise, tests, case.files, runner)
        seconds = time.perf_counter() - started
        target = next((c for c in report.checks if c.id == case.fails), None)
        if report.status is GradeStatus.ERRORED or target is None:
            results.append(
                CaseResult(exercise.id, case.name, False, report.error or "no result", seconds)
            )
        elif target.passed:
            results.append(
                CaseResult(exercise.id, case.name, False, f"'{case.fails}' passed", seconds)
            )
        elif case.message_contains not in target.message:
            results.append(
                CaseResult(
                    exercise.id,
                    case.name,
                    False,
                    f"message lacks {case.message_contains!r}: {target.message!r}",
                    seconds,
                )
            )
        else:
            results.append(CaseResult(exercise.id, case.name, True, target.message, seconds))
    return results
