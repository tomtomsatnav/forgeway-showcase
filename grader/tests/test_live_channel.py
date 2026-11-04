"""The harness's side of an in-app live run: the child, the relay and what it refuses (ADR 0012).

Each case runs the real harness in a subprocess with a live header, and plays the worker: it
answers each call frame on the harness's stdin and reads the final report.
"""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import tarfile
import textwrap
from pathlib import Path
from typing import Any

NONCE = "be" * 16
REPLY = {
    "text": "a real answer",
    "stop_reason": "end_turn",
    "usage": {"input_tokens": 12, "output_tokens": 4, "cache_read_input_tokens": 0},
    "tool_calls": [],
    "model": "claude-haiku-5-5",
    "latency_ms": 321.0,
}

ASKS = textwrap.dedent(
    """
    import os
    from forgeway_kit import Message, default_client

    client = default_client()
    reply = client.complete([Message("user", "hi")], max_tokens=99999, model="gpt-anything")
    print(reply.text, reply.model, reply.usage.input_tokens)
    streamed = "".join(
        e.text for e in client.stream([Message("user", "again")]) if hasattr(e, "text")
    )
    print("streamed:", streamed)
    try:
        from forgeway_kit.live import OpenAIClient
        OpenAIClient("any", base_url="http://127.0.0.1:9")
    except RuntimeError as exc:
        print("live client:", exc)
    print("env:", sorted(os.environ))
    """
)


def start(tmp_path: Path, files: dict[str, str], timeout_s: float = 20) -> subprocess.Popen[bytes]:
    archive = io.BytesIO()
    manifest = {"checks": [], "live": {"timeout_s": timeout_s, "max_output_bytes": 2000}}
    entries = {"manifest.json": json.dumps(manifest)}
    entries.update({f"submission/{k}": v for k, v in files.items()})
    with tarfile.open(fileobj=archive, mode="w") as tar:
        for name, text in entries.items():
            data = text.encode()
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    work = tmp_path / "work"
    work.mkdir()
    env = {
        "PATH": os.defpath,
        "LATTICE_WORKDIR": str(work),
        "PYTHONHASHSEED": "0",
        "FORGEWAY_LIVE": "anthropic",  # ignored: the proxy client is configured explicitly
        "ANTHROPIC_API_KEY": "sk-ant-host-only",  # never reaches the child's environment
    }
    process = subprocess.Popen(
        [sys.executable, "-I", "-m", "lattice_grader.harness"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )
    assert process.stdin
    body = archive.getvalue()
    process.stdin.write(f"{NONCE} live {len(body)}\n".encode() + body)
    process.stdin.flush()
    return process


def serve(process: subprocess.Popen[bytes]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Answer every call with `REPLY`; return the calls and the final report."""
    assert process.stdin and process.stdout
    calls = []
    for raw in process.stdout:
        line = raw.decode()
        prefix = f"LATTICE-LIVE {NONCE} "
        assert line.startswith(prefix), line
        message = json.loads(line[len(prefix) :])
        if message["type"] == "done":
            process.stdin.close()
            process.wait(timeout=10)
            return calls, message
        calls.append(message)
        reply = {"id": message["id"], "completion": REPLY}
        process.stdin.write(json.dumps(reply).encode() + b"\n")
        process.stdin.flush()
    raise AssertionError(f"no report: {process.stderr.read().decode() if process.stderr else ''}")


def test_learner_code_reaches_the_model_only_through_the_proxy_client(tmp_path: Path) -> None:
    calls, done = serve(start(tmp_path, {"live.py": ASKS}))
    assert done["exit_status"] == 0, done
    assert [c["id"] for c in calls] == [1, 2]
    request = calls[0]["request"]
    # The toolkit's arguments as asked; the worker forces the model and clamps max_tokens.
    assert request["model"] == "gpt-anything"
    assert request["max_tokens"] == 99999
    assert request["messages"] == [
        {"role": "user", "content": "hi", "tool_calls": [], "tool_call_id": None}
    ]
    stdout = done["stdout"]
    assert "a real answer claude-haiku-5-5 12" in stdout
    assert "streamed: a real answer" in stdout
    assert "live client: live clients are never used while grading" in stdout
    assert "ANTHROPIC_API_KEY" not in stdout
    assert "FORGEWAY_GRADING" in stdout


def test_a_message_that_is_not_a_call_stops_the_run(tmp_path: Path) -> None:
    forged = textwrap.dedent(
        """
        import os
        for fd in range(3, 12):
            try:
                os.write(fd, b'{"id": 1, "request": {}, "to": "http://elsewhere"}\\n')
            except OSError:
                pass
        import time
        time.sleep(5)
        """
    )
    calls, done = serve(start(tmp_path, {"live.py": forged}))
    assert calls == []
    assert done["error"] == "bad-message"


def test_an_oversized_message_stops_the_run(tmp_path: Path) -> None:
    huge = textwrap.dedent(
        """
        from forgeway_kit import Message, default_client
        default_client().complete([Message("user", "x" * 600_000)])
        """
    )
    calls, done = serve(start(tmp_path, {"live.py": huge}))
    assert calls == []
    assert done["error"] == "bad-message"


def test_an_exercise_without_live_py_says_so(tmp_path: Path) -> None:
    calls, done = serve(start(tmp_path, {"agent.py": "x = 1\n"}))
    assert calls == []
    assert done["error"] == "no-live-script"


def test_a_run_past_its_time_is_stopped_with_its_output(tmp_path: Path) -> None:
    loop = "print('started', flush=True)\nwhile True:\n    pass\n"
    _calls, done = serve(start(tmp_path, {"live.py": loop}, timeout_s=1))
    assert done["timed_out"] is True
    assert done["stdout"] == "started\n"


def test_output_is_bounded(tmp_path: Path) -> None:
    _calls, done = serve(start(tmp_path, {"live.py": "print('y' * 10_000)\n"}))
    assert len(done["stdout"]) == 2000
    assert done["stdout_truncated"] is True


def test_a_crash_is_reported_with_its_traceback(tmp_path: Path) -> None:
    _calls, done = serve(start(tmp_path, {"live.py": "raise ValueError('boom')\n"}))
    assert done["exit_status"] == 1
    assert "ValueError: boom" in done["stderr"]
