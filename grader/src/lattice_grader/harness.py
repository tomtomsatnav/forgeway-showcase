"""Sandbox entrypoint: ``python -m lattice_grader.harness``.

Reads the nonce as the first line of stdin, then a tar archive containing ``manifest.json``,
``submission/`` and ``tests/``, extracts it into the writable work directory, runs the declared
checks and prints a single report line. The nonce never enters the environment, so learner code
cannot read it from ``/proc/self/environ``. Once pytest has collected the hidden tests, their
files are deleted from the work directory: the test modules stay in memory, and `run_fresh`
children get their source from `lattice_grader.isolation` instead of the file.

In the sandbox this runs as user 10001, started by `lattice_grader.launcher`, which runs learner
code for `isolation: process` exercises as user 10002: the tests directory is made 0700 here, so
that code cannot read it even before it is deleted.

Learner code may not use the grader's own code, whose reference implementations hidden tests
import. A submission whose text names ``lattice_grader`` fails every check without running. That
test reads text only, so `lattice_grader.guard` also refuses the import itself when a submission
file makes it, however the name is spelt.
"""

from __future__ import annotations

import io
import json
import os
import shutil
import sys
import tarfile
import tempfile
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest

from lattice_grader import bridge, guard, isolation, launcher
from lattice_grader.plugin import ReportPlugin
from lattice_grader.report import CheckOutcome, HarnessReport

MAX_ARCHIVE_BYTES = 8 * 1024 * 1024
MAX_NONCE_BYTES = 128
EMPTY_INI = Path(__file__).with_name("pytest.ini")


class _UnlinkHiddenTests:
    """Deletes the hidden tests from disk once pytest has imported them.

    Learner code runs only after collection, so it never finds the test files to read expected
    values from. Their source is kept in memory first, for `run_fresh`.
    """

    def __init__(self, tests: Path) -> None:
        self._tests = tests

    def pytest_collection_finish(self, session: pytest.Session) -> None:
        isolation.remember_sources(
            {
                str(path.resolve()): path.read_text(encoding="utf-8")
                for path in self._tests.rglob("*.py")
            }
        )
        shutil.rmtree(self._tests, ignore_errors=True)


class _ShareTmpPath:
    """Opens each test's `tmp_path` to learner code running as the second user.

    pytest makes its temporary directories private (0700). A test that hands learner code a path
    under `tmp_path` (a corpus file, a log for a server that learner code starts) means it to be
    used, as it could be in-process. So the directory itself becomes 0777, and the directories
    above it 0711: passable, but not listable, so other tests' directories stay unseen.
    """

    @pytest.hookimpl(hookwrapper=True)
    def pytest_fixture_setup(
        self, fixturedef: pytest.FixtureDef[Any], request: pytest.FixtureRequest
    ) -> Generator[None, Any, None]:
        outcome = yield
        if fixturedef.argname not in {"tmp_path", "tmpdir"} or outcome.excinfo is not None:
            return
        path = Path(str(outcome.get_result()))
        path.chmod(0o777)  # shared with learner code on purpose
        top = Path(tempfile.gettempdir())
        for parent in path.parents:
            if parent == top or parent.stat().st_uid != os.getuid():
                break
            parent.chmod(0o711)


def main() -> int:
    work = Path(os.environ.get("LATTICE_WORKDIR", "/work"))
    nonce = sys.stdin.buffer.readline(MAX_NONCE_BYTES).decode("ascii", errors="replace").strip()
    if not nonce:
        print("no nonce on stdin", file=sys.stderr)
        return 2

    archive = sys.stdin.buffer.read(MAX_ARCHIVE_BYTES + 1)
    if len(archive) > MAX_ARCHIVE_BYTES:
        print("archive too large", file=sys.stderr)
        return 2
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        tar.extractall(work, filter="data")
    # Learner code in a bridge child runs as another user (`lattice_grader.launcher`): it may read
    # the submission (0755 directories, 0644 files) but not the hidden tests or the manifest.
    (work / "tests").mkdir(exist_ok=True)
    (work / "tests").chmod(0o700)
    (work / "manifest.json").chmod(0o600)

    manifest = json.loads((work / "manifest.json").read_text())
    checks: dict[str, str] = {c["id"]: c["test"] for c in manifest["checks"]}
    submission = work / "submission"
    named = _files_naming_grader(submission)
    if named:
        message = (
            f"{guard.MESSAGE} It is named in {', '.join(named)}: remove every mention of it, "
            "comments included, and build on forgeway_kit and the standard library instead."
        )
        outcomes = [CheckOutcome(check_id, "failed", message) for check_id in checks]
        print(HarnessReport(checks=outcomes, exit_status=1).to_line(nonce), flush=True)
        return 0
    # Isolation mode (ADR 0009): "process" runs learner code in a child interpreter.
    process_bridge = None
    if manifest.get("isolation") == "process":
        process_bridge = bridge.install(submission)
        if launcher.available():
            # Learner code runs as another user. What the tests create from here on (files and
            # directories under `tmp_path`, a server's log) is shared with it, as it would be
            # in-process: the hidden tests and the manifest were made private above.
            os.umask(0)
    else:
        guard.install([submission])
        sys.path.insert(0, str(submission))

    # Keep a private copy of stdout for the report, then point fd 1 at /dev/null so neither
    # pytest's own output nor anything learner code writes can reach the worker.
    report_stream = os.fdopen(os.dup(1), "w")
    devnull = os.open(os.devnull, os.O_WRONLY)
    os.dup2(devnull, 1)

    plugin = ReportPlugin(checks, submission)
    exit_status = pytest.main(
        [
            "-c",
            str(EMPTY_INI),
            "--rootdir",
            str(work / "tests"),
            "-p",
            "no:cacheprovider",
            "--assert=plain",
            "--import-mode=importlib",
            "-q",
            "--no-header",
            "--tb=no",
            "--continue-on-collection-errors",
            *(str(work / "tests" / nodeid) for nodeid in dict.fromkeys(checks.values())),
        ],
        plugins=[
            plugin,
            _UnlinkHiddenTests(work / "tests"),
            *([_ShareTmpPath()] if process_bridge is not None and launcher.available() else []),
        ],
    )
    if process_bridge is not None:
        process_bridge.close()
    report = HarnessReport(checks=plugin.finalise(), exit_status=int(exit_status))
    report_stream.write(report.to_line(nonce) + "\n")
    report_stream.flush()
    return 0


def _files_naming_grader(submission: Path) -> list[str]:
    """Submission files whose text contains the grader's package name, sorted."""
    return sorted(
        path.relative_to(submission).as_posix()
        for path in submission.rglob("*")
        if path.is_file() and guard.PACKAGE in path.read_text(encoding="utf-8", errors="replace")
    )


if __name__ == "__main__":
    raise SystemExit(main())
