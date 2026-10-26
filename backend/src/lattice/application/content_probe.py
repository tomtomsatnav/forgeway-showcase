"""Grade adversarial probes against an exercise for real and keep every check's outcome.

A probe is a set of learner files: the shortcut an author wants to prove fails. It is laid over
the starter (as a learner's submission is) or over the reference solution, so a probe can change
one function of a working answer.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

from lattice.domain.content import GradingAssets
from lattice.domain.grading import GradeReport, SandboxRunner, SubmissionError, grade_submission


class ProbeBase(StrEnum):
    STARTER = "starter"
    SOLUTION = "solution"


@dataclass(frozen=True)
class ProbeResult:
    name: str
    report: GradeReport | None  # None when the submission was refused before grading
    refused: str | None = None


def probe_exercise(
    source: GradingAssets,
    probes: Mapping[str, Mapping[str, str]],
    runner: SandboxRunner,
    *,
    base: ProbeBase = ProbeBase.STARTER,
) -> list[ProbeResult]:
    """Grade each probe (name -> files) and return its full report, in the order given."""
    exercise = source.exercise
    tests = source.tests()
    under: dict[str, str] = {}
    if base is ProbeBase.SOLUTION:
        solution = source.solution()
        under = {path: solution[path] for path in exercise.editable if path in solution}
    results: list[ProbeResult] = []
    for name, files in probes.items():
        try:
            report = grade_submission(exercise, tests, {**under, **files}, runner)
        except SubmissionError as err:
            results.append(ProbeResult(name, None, str(err)))
            continue
        results.append(ProbeResult(name, report))
    return results
