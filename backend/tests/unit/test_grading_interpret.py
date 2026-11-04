import json

import pytest

from lattice.domain.content import Exercise
from lattice.domain.grading import GradeStatus, SandboxResult, SubmissionError
from lattice.domain.grading.service import interpret, validate_submission

NONCE = "abc123"


@pytest.fixture
def exercise() -> Exercise:
    return Exercise(
        id="test.two-checks",
        version=1,
        title="Two checks",
        branch="test",
        tier="beginner",
        xp=10,
        editable=("solution.py",),
        checks=(
            {"id": "first", "title": "First", "test": "test_it.py::test_first"},
            {"id": "second", "title": "Second", "test": "test_it.py::test_second"},
        ),
        limits={"timeout_s": 5, "memory_mb": 128},
        brief="",
        starter_files={"solution.py": ""},
        content_hash="0" * 64,
    )


def report_line(outcomes: dict[str, str], exit_status: int, nonce: str = NONCE) -> str:
    checks = [{"id": cid, "outcome": o, "message": f"{cid} msg"} for cid, o in outcomes.items()]
    return f"LATTICE-REPORT {nonce} {json.dumps({'checks': checks, 'exit_status': exit_status})}"


def result(stdout: str = "", **overrides) -> SandboxResult:
    fields = {
        "exit_code": 0,
        "stdout": stdout,
        "stderr": "",
        "timed_out": False,
        "output_truncated": False,
        "duration_ms": 12,
        **overrides,
    }
    return SandboxResult(**fields)


def test_all_checks_passing_is_a_pass_in_declared_order(exercise):
    line = report_line({"second": "passed", "first": "passed"}, 0)
    report = interpret(exercise, result(line), NONCE)
    assert report.status is GradeStatus.PASSED
    assert [c.id for c in report.checks] == ["first", "second"]
    assert report.checks[0].title == "First"


def test_any_failing_check_fails_the_attempt_and_keeps_messages(exercise):
    report = interpret(
        exercise, result(report_line({"first": "passed", "second": "failed"}, 1)), NONCE
    )
    assert report.status is GradeStatus.FAILED
    assert report.checks[1].message == "second msg"


def test_timeout_is_a_learner_failure_with_guidance(exercise):
    report = interpret(exercise, result(timed_out=True), NONCE)
    assert report.status is GradeStatus.FAILED
    assert all("longer than 5 seconds" in c.message for c in report.checks)


def test_out_of_memory_kill_is_explained(exercise):
    report = interpret(exercise, result(exit_code=137), NONCE)
    assert report.status is GradeStatus.FAILED
    assert "128 MB" in report.checks[0].message


def test_flooded_output_is_a_learner_failure(exercise):
    assert interpret(exercise, result(output_truncated=True), NONCE).status is GradeStatus.FAILED


@pytest.mark.parametrize(
    "stdout",
    [
        "",
        report_line({"first": "passed", "second": "passed"}, 0, nonce="forged"),
        "\n".join([report_line({"first": "passed", "second": "passed"}, 0)] * 2),
        report_line({"first": "passed"}, 0),
        report_line({"first": "passed", "second": "passed"}, 1),
        report_line({"first": "failed", "second": "failed"}, 0),
        f"LATTICE-REPORT {NONCE} not-json",
    ],
    ids=[
        "missing",
        "wrong-nonce",
        "duplicate",
        "missing-check",
        "exit-says-failed",
        "exit-says-passed",
        "malformed",
    ],
)
def test_inconsistent_reports_are_errored_never_passed(exercise, stdout):
    report = interpret(exercise, result(stdout), NONCE)
    assert report.status is GradeStatus.ERRORED
    assert "does not count against you" in (report.error or "")


def test_only_editable_files_may_be_submitted(exercise):
    with pytest.raises(SubmissionError, match=r"conftest\.py"):
        validate_submission(exercise, {"solution.py": "", "conftest.py": "import os"})


def test_oversized_files_are_rejected(exercise):
    with pytest.raises(SubmissionError, match="larger than"):
        validate_submission(exercise, {"solution.py": "x" * 70_000})
