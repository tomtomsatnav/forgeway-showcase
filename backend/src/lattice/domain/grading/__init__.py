"""Grading contracts: what a grade looks like and the port a sandbox must implement."""

from lattice.domain.grading.model import (
    CheckResult,
    GradeReport,
    GradeStatus,
    SandboxRequest,
    SandboxResult,
    SandboxRunner,
)
from lattice.domain.grading.service import SubmissionError, grade_submission

__all__ = [
    "CheckResult",
    "GradeReport",
    "GradeStatus",
    "SandboxRequest",
    "SandboxResult",
    "SandboxRunner",
    "SubmissionError",
    "grade_submission",
]
