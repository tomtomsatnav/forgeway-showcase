"""A pytest plugin that turns test results into learner-facing check outcomes."""

from __future__ import annotations

import textwrap
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest

from lattice_grader.bridge import LearnerProcessError
from lattice_grader.report import CheckOutcome, clip


class ReportPlugin:
    """Collects one outcome per declared check.

    Failure messages are written for learners: an assertion's own message (tests use
    ``assert ok, "helpful explanation"``), or for an exception raised by learner code, its
    type, message and the learner-owned frames. Grader source and frames are never shown.
    """

    def __init__(self, checks: dict[str, str], submission_dir: Path) -> None:
        self._check_by_nodeid = {nodeid: check_id for check_id, nodeid in checks.items()}
        self._submission_dir = submission_dir.resolve()
        self.outcomes: dict[str, CheckOutcome] = {}
        self._collection_errors: dict[str, str] = {}

    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_makereport(
        self, item: pytest.Item, call: pytest.CallInfo[None]
    ) -> Generator[None, Any, None]:
        outcome = yield
        report: pytest.TestReport = outcome.get_result()
        # A check names a test function; parametrised cases ("test_x[a]") all count towards it.
        check_id = self._check_by_nodeid.get(item.nodeid) or self._check_by_nodeid.get(
            item.nodeid.split("[", 1)[0]
        )
        if check_id is None:
            return
        existing = self.outcomes.get(check_id)
        if existing is not None and existing.outcome == "failed":
            return  # the first failure is the one the learner sees
        if report.failed:
            message = self._describe(call.excinfo) if call.excinfo else "Check failed."
            self.outcomes[check_id] = CheckOutcome(
                check_id, "failed", clip(message), clip(report.capstdout)
            )
        elif report.when == "call" and report.passed and existing is None:
            self.outcomes[check_id] = CheckOutcome(
                check_id, "passed", output=clip(report.capstdout)
            )

    def pytest_collectreport(self, report: pytest.CollectReport) -> None:
        if report.failed:
            self._collection_errors[report.nodeid] = str(report.longrepr)

    def finalise(self) -> list[CheckOutcome]:
        """Outcomes for every declared check, in declaration order."""
        results = []
        for nodeid, check_id in self._check_by_nodeid.items():
            if check_id in self.outcomes:
                results.append(self.outcomes[check_id])
                continue
            test_file = nodeid.split("::", 1)[0]
            error = self._collection_errors.get(test_file)
            message = (
                self._describe_collection_error(error)
                if error
                else "This check did not run. Make sure your code imports cleanly."
            )
            results.append(CheckOutcome(check_id, "failed", clip(message)))
        return results

    def _describe(self, excinfo: pytest.ExceptionInfo[BaseException]) -> str:
        exc = excinfo.value
        if isinstance(exc, AssertionError | LearnerProcessError):
            return str(exc) or "Check failed."
        # Learner code in another process (ADR 0009): the bridge brings its frames back.
        frames = exc.__dict__.get("__learner_frames__") or [
            f"  {Path(entry.path).relative_to(self._submission_dir)}, line {entry.lineno + 1}, "
            f"in {entry.name}"
            for entry in excinfo.traceback
            if self._is_learner_file(entry.path)
        ]
        detail = f"{type(exc).__name__}: {exc}"
        if not frames:
            return f"Your code raised {detail}"
        return f"Your code raised {detail}\n" + "\n".join(frames[-5:])

    def _describe_collection_error(self, error: str) -> str:
        # Collection errors come from importing learner code (syntax errors, bad imports).
        # Keep only the lines that mention learner files or the final error line.
        lines = [line for line in error.splitlines() if line.strip()]
        relevant = [ln for ln in lines if str(self._submission_dir) in ln or ln.startswith("E ")]
        cleaned = [
            ln.replace(str(self._submission_dir) + "/", "").removeprefix("E").rstrip()
            for ln in relevant
        ]
        excerpt = textwrap.dedent("\n".join(cleaned[-6:] or lines[-1:]))
        return "Your code could not be imported:\n" + excerpt

    def _is_learner_file(self, path: str | Path) -> bool:
        try:
            Path(path).resolve().relative_to(self._submission_dir)
        except ValueError:
            return False
        return True
