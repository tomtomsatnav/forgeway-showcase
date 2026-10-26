"""A stdio relay that logs every line between a client and the server it starts.

Run as ``python -m lattice_grader.project_research_reference.tap LOG -- ARGV...``. It starts
``ARGV`` as a child process and copies lines both ways unchanged: its own stdin to the child's
stdin and the child's stdout to its own stdout, flushing each line. Every line is first appended
to ``LOG`` as one JSON object, ``{"dir": "in" | "out", "line": <text without the newline>}``,
where ``in`` means client to server. When its stdin closes it closes the child's stdin, waits for
the child and exits with the child's status.
"""

from __future__ import annotations

import contextlib
import json
import subprocess
import sys
import threading
from collections.abc import Sequence
from pathlib import Path
from typing import IO, Any

MODULE = "lattice_grader.project_research_reference.tap"


def tap_argv(log: Path | str, argv: Sequence[str], python: str | None = None) -> list[str]:
    """The argv that starts ``argv`` behind a tap writing to ``log``."""
    return [python or sys.executable, "-m", MODULE, str(log), "--", *argv]


def read_log(log: Path | str) -> list[dict[str, Any]]:
    """The logged lines, in order; lines that are not JSON objects keep only their text."""
    path = Path(log)
    if not path.exists():
        return []
    entries: list[dict[str, Any]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        entry = json.loads(raw)
        try:
            message = json.loads(entry["line"])
        except ValueError:
            message = None
        entries.append(
            {
                "dir": entry["dir"],
                "line": entry["line"],
                "message": message if isinstance(message, dict) else None,
            }
        )
    return entries


def tool_calls(log: Path | str) -> list[dict[str, Any]]:
    """Every ``tools/call`` request that reached the server: ``{"name", "arguments", "meta"}``."""
    calls = []
    for entry in read_log(log):
        message = entry["message"]
        if entry["dir"] != "in" or message is None or message.get("method") != "tools/call":
            continue
        params = message.get("params") if isinstance(message.get("params"), dict) else {}
        calls.append(
            {
                "name": params.get("name"),
                "arguments": params.get("arguments"),
                "meta": params.get("_meta"),
            }
        )
    return calls


class _Log:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = threading.Lock()

    def write(self, direction: str, line: str) -> None:
        record = json.dumps({"dir": direction, "line": line.rstrip("\n")}) + "\n"
        with self._lock, self._path.open("a", encoding="utf-8") as handle:
            handle.write(record)


def _pipe[T](pipe: T | None) -> T:
    if pipe is None:
        raise RuntimeError("the child process was started without this pipe")
    return pipe


def _forward_input(log: _Log, source: IO[str], sink: IO[str]) -> None:
    for line in source:
        log.write("in", line)
        try:
            sink.write(line)
            sink.flush()
        except (BrokenPipeError, ValueError):
            break
    with contextlib.suppress(BrokenPipeError, ValueError):
        sink.close()


def main(argv: Sequence[str]) -> int:
    if len(argv) < 3 or argv[1] != "--":
        print("usage: tap LOG -- ARGV...", file=sys.stderr)
        return 2
    log = _Log(Path(argv[0]))
    child = subprocess.Popen(  # noqa: S603 - argv comes from the grader's own tests
        list(argv[2:]),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        bufsize=1,
    )
    stdin, stdout = _pipe(child.stdin), _pipe(child.stdout)
    feeder = threading.Thread(target=_forward_input, args=(log, sys.stdin, stdin), daemon=True)
    feeder.start()
    for line in stdout:
        log.write("out", line)
        try:
            sys.stdout.write(line)
            sys.stdout.flush()
        except (BrokenPipeError, ValueError):
            break
    status = child.wait()
    return status


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
