"""The harness's side of an in-app live run (ADR 0012).

A live run executes the exercise's `live.py` over the learner's files against a real model. The
model is reached only through the worker, outside the sandbox: the container keeps no network,
and holds no key.

The harness starts the learner's program in a child interpreter (`child.py`, as the learner's
user where the launcher serves the sandbox) on a pair of pipes, and relays between that child
and the worker over the container's own stdin and stdout:

- child to harness: ``{"id": n, "request": {...}}``, one JSON object per line. Each line is
  untrusted: at most `MAX_REQUEST_BYTES`, an object with exactly those keys, `id` counting up
  from 1 and `request` an object. Anything else stops the run.
- harness to worker: ``LATTICE-LIVE <nonce> {"type": "call", "id": n, "request": {...}}``. The
  worker checks the request again, in full, and answers on stdin with one line, which the
  harness passes back to the child.
- when the child exits (or runs out of time), the harness sends ``{"type": "done", ...}`` with
  its exit status and the start of what it wrote to stdout and stderr.
"""

from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import threading
import time
from collections.abc import Mapping
from pathlib import Path
from typing import IO, Any

from lattice_grader import launcher

PREFIX = "LATTICE-LIVE"
MAX_REQUEST_BYTES = 512 * 1024
MAX_REPLY_BYTES = 4 * 1024 * 1024
DEFAULT_TIMEOUT_S = 60.0
DEFAULT_MAX_OUTPUT_BYTES = 16 * 1024
SCRIPT = "live.py"
OUTPUT_DIR = ".live"

_EOF = object()
_TOO_LARGE = object()


class LiveRun:
    """One live run: the child, the relay loop and the final report."""

    def __init__(
        self,
        work: Path,
        nonce: str,
        settings: Mapping[str, Any],
        inbound: IO[bytes],
        outbound: IO[str],
    ) -> None:
        self.submission = work / "submission"
        self.output = work / OUTPUT_DIR
        self.nonce = nonce
        self.timeout_s = float(settings.get("timeout_s", DEFAULT_TIMEOUT_S))
        self.max_output = int(settings.get("max_output_bytes", DEFAULT_MAX_OUTPUT_BYTES))
        self.inbound = inbound
        self.outbound = outbound

    def run(self) -> int:
        if not (self.submission / SCRIPT).is_file():
            self._send({"type": "done", "exit_status": None, "error": "no-live-script"})
            return 0
        self._prepare_output()
        process = self._start()
        assert process.stdin and process.stdout  # noqa: S101 - set by the launcher or PIPE
        lines: queue.Queue[object] = queue.Queue()
        threading.Thread(target=_read_lines, args=(process.stdout, lines), daemon=True).start()
        deadline = time.monotonic() + self.timeout_s
        timed_out, error, expected = False, None, 1
        while True:
            try:
                item = lines.get(timeout=max(deadline - time.monotonic(), 0.001))
            except queue.Empty:
                timed_out = True
                break
            if item is _EOF:
                break
            call = self._parse(item, expected)
            if call is None:
                error = "bad-message"
                break
            expected += 1
            self._send({"type": "call", "id": call[0], "request": call[1]})
            reply = self.inbound.readline(MAX_REPLY_BYTES + 1)
            if not reply or len(reply) > MAX_REPLY_BYTES:
                error = "channel-closed"
                break
            try:
                process.stdin.write(reply if reply.endswith(b"\n") else reply + b"\n")
                process.stdin.flush()
            except (BrokenPipeError, ValueError):
                break  # the child exited between its request and our reply
        status: int | None = None
        if not timed_out and error is None:  # the child closed the channel: let it finish
            try:
                status = process.wait(timeout=max(deadline - time.monotonic(), 1.0))
            except subprocess.TimeoutExpired:
                timed_out = True
        if status is None:
            process.kill()
            try:
                status = process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                status = None
        stdout, stdout_cut = self._read_output("stdout")
        stderr, stderr_cut = self._read_output("stderr")
        self._send(
            {
                "type": "done",
                "exit_status": status,
                "timed_out": timed_out,
                "error": error,
                "stdout": stdout,
                "stderr": stderr,
                "stdout_truncated": stdout_cut,
                "stderr_truncated": stderr_cut,
            }
        )
        return 0

    def _prepare_output(self) -> None:
        # Ours, so the learner's user cannot swap the files for links; theirs to write.
        self.output.mkdir(mode=0o755, exist_ok=True)
        self.output.chmod(0o755)
        for name in ("stdout", "stderr"):
            path = self.output / name
            path.touch()
            path.chmod(0o666)

    def _start(self) -> subprocess.Popen[bytes] | launcher.LaunchedProcess:
        source = Path(__file__).with_name("child.py").read_text(encoding="utf-8")
        config = {
            "root": str(self.submission),
            "script": str(self.submission / SCRIPT),
            "stdout": str(self.output / "stdout"),
            "stderr": str(self.output / "stderr"),
        }
        program = f"{source}\nmain({config!r})\n"
        env = {
            "PATH": os.defpath,
            "PYTHONHASHSEED": "0",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONIOENCODING": "utf-8",
            "PYTHONUNBUFFERED": "1",
            "FORGEWAY_GRADING": "1",  # forgeway_kit's live clients refuse to be built here
        }
        argv = [sys.executable, "-s", "-P", "-c", program]
        if launcher.available():
            return launcher.launch(argv, env=env, cwd=str(self.submission))
        return subprocess.Popen(  # noqa: S603 - argv list, no shell
            argv,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            env=env,
            cwd=self.submission,
            close_fds=True,
        )

    def _parse(self, item: object, expected: int) -> tuple[int, dict[str, Any]] | None:
        """A child line as (id, request), or None if it is anything but a well-formed call."""
        if not isinstance(item, bytes):
            return None
        try:
            message = json.loads(item)
        except ValueError:
            return None
        if not isinstance(message, dict) or set(message) != {"id", "request"}:
            return None
        call_id, request = message["id"], message["request"]
        if type(call_id) is not int or call_id != expected or not isinstance(request, dict):
            return None
        return call_id, request

    def _read_output(self, name: str) -> tuple[str, bool]:
        try:
            fd = os.open(self.output / name, os.O_RDONLY | os.O_NOFOLLOW)
        except OSError:
            return "", False
        with os.fdopen(fd, "rb") as file:
            data = file.read(self.max_output + 1)
        return data[: self.max_output].decode("utf-8", errors="replace"), len(
            data
        ) > self.max_output

    def _send(self, message: Mapping[str, Any]) -> None:
        self.outbound.write(f"{PREFIX} {self.nonce} {json.dumps(message)}\n")
        self.outbound.flush()


def _read_lines(stream: IO[bytes], lines: queue.Queue[object]) -> None:
    while True:
        line = stream.readline(MAX_REQUEST_BYTES + 1)
        if not line:
            lines.put(_EOF)
            return
        if len(line) > MAX_REQUEST_BYTES:
            lines.put(_TOO_LARGE)
            return
        lines.put(line)


def run(
    work: Path, nonce: str, settings: Mapping[str, Any], inbound: IO[bytes], outbound: IO[str]
) -> int:
    """Run `submission/live.py` against the worker's proxy and report on `outbound`."""
    return LiveRun(work, nonce, settings, inbound, outbound).run()
