"""The launcher's pieces that run anywhere.

Starting processes as another user needs root, so the end-to-end proof is a Docker test in
backend/tests/integration/test_sandbox_hostile.py
(`test_out_of_process_learner_code_cannot_reach_the_tests_or_the_grader`).
"""

from __future__ import annotations

import os
import signal
import socket
import subprocess
import sys

import pytest

from lattice_grader import launcher


def launched(status_line: bytes | None = None) -> tuple[launcher.LaunchedProcess, socket.socket]:
    ours, theirs = socket.socketpair()
    read_fd, write_fd = os.pipe()
    process = launcher.LaunchedProcess(
        ours, 42, os.fdopen(write_fd, "wb"), os.fdopen(read_fd, "rb")
    )
    if status_line is not None:
        theirs.sendall(status_line)
    return process, theirs


def test_the_exit_status_arrives_over_the_connection() -> None:
    process, theirs = launched()
    assert process.poll() is None
    with pytest.raises(subprocess.TimeoutExpired):
        process.wait(timeout=0.05)
    theirs.sendall(b'{"status": 3}\n')
    assert process.wait(timeout=1) == 3
    assert process.poll() == 3 and process.returncode == 3


def test_a_status_split_across_reads_is_put_back_together() -> None:
    process, theirs = launched(b'{"stat')
    assert process.poll() is None
    theirs.sendall(b'us": -9}\n')
    assert process.wait(timeout=1) == -signal.SIGKILL


def test_killing_is_a_request_to_the_launcher() -> None:
    process, theirs = launched()
    process.kill()
    assert theirs.recv(64) == b"kill\n"


def test_a_launcher_that_goes_away_counts_as_the_child_killed() -> None:
    process, theirs = launched()
    theirs.close()
    assert process.wait(timeout=1) == -signal.SIGKILL
    process.kill()  # harmless once the connection is gone


def test_without_a_launcher_the_bridge_starts_children_itself(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(launcher.SOCKET_ENV, raising=False)
    assert launcher.available() is False
    monkeypatch.setenv(launcher.SOCKET_ENV, launcher.SOCKET)
    assert launcher.available() is True


@pytest.mark.parametrize(
    ("code", "expected"),
    [("import os; os._exit(3)", 3), ("import os, signal; os.kill(os.getpid(), 9)", -9)],
)
def test_wait_statuses_read_as_popen_return_codes(code: str, expected: int) -> None:
    pid = os.posix_spawn(sys.executable, [sys.executable, "-c", code], dict(os.environ))
    _, status = os.waitpid(pid, 0)
    assert launcher._status(status) == expected
