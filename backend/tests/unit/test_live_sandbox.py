"""The live runner's side of the channel, against a stand-in `docker` that plays the container.

The stand-in records the arguments and environment it was started with, so these tests prove
the platform key is in neither, and it can break the channel's rules in each way a compromised
container could.
"""

from __future__ import annotations

import json
import sys
import textwrap
from pathlib import Path
from typing import Any

import pytest

from lattice.domain.live import LiveSandboxRequest
from lattice.infrastructure.sandbox_docker import (
    MAX_LIVE_LINE_BYTES,
    DockerSandboxConfig,
    DockerSandboxRunner,
    build_live_archive,
)

KEY = "sk-ant-platform-key-never-in-a-sandbox"

FAKE_DOCKER = """#!{python}
import json, os, sys, time
from pathlib import Path
here = Path(__file__)
if sys.argv[1] == "kill":  # `docker kill <name>` stops the run, as the daemon would
    os.kill(int(here.with_suffix(".pid").read_text()), 9)
    sys.exit(0)
here.with_suffix(".pid").write_text(str(os.getpid()))
here.with_suffix(".argv").write_text(json.dumps(sys.argv))
here.with_suffix(".env").write_text(json.dumps(dict(os.environ)))
nonce, _, size = sys.stdin.buffer.readline().decode().split()
archive = sys.stdin.buffer.read(int(size))
here.with_suffix(".tar").write_bytes(archive)
def send(message, prefix=f"LATTICE-LIVE {{nonce}} "):
    sys.stdout.write(prefix + json.dumps(message) + "\\n")
    sys.stdout.flush()
{scenario}
"""

SCENARIOS = {
    "ok": """
send({"type": "call", "id": 1, "request": {"messages": []}})
reply = json.loads(sys.stdin.readline())
send({"type": "done", "exit_status": 0, "stdout": json.dumps(reply), "stderr": ""})
""",
    "wrong-nonce": """
send({"type": "call", "id": 1, "request": {}}, prefix="LATTICE-LIVE 0000 ")
time.sleep(30)
""",
    "skips-an-id": """
send({"type": "call", "id": 2, "request": {}})
time.sleep(30)
""",
    "not-json": """
sys.stdout.write(f"LATTICE-LIVE {nonce} not json\\n"); sys.stdout.flush()
time.sleep(30)
""",
    "oversized": f"""
send({{"type": "call", "id": 1, "request": {{"x": "y" * {MAX_LIVE_LINE_BYTES}}}}})
time.sleep(30)
""",
    "unknown-type": """
send({"type": "fetch", "id": 1, "url": "http://169.254.169.254/"})
time.sleep(30)
""",
    "silent": """
time.sleep(30)
""",
}


def runner(tmp_path: Path, scenario: str) -> tuple[DockerSandboxRunner, Path]:
    docker = tmp_path / "docker"
    docker.write_text(
        FAKE_DOCKER.format(python=sys.executable, scenario=textwrap.dedent(SCENARIOS[scenario]))
    )
    docker.chmod(0o755)
    config = DockerSandboxConfig(
        images={"python": "lattice-sandbox-python:test"},
        docker_binary=str(docker),
        startup_allowance_s=0.5,
    )
    return DockerSandboxRunner(config), docker


REQUEST = LiveSandboxRequest(
    runtime="python",
    files={"agent.py": "x = 1\n", "live.py": "print('hi')\n"},
    nonce="ab" * 16,
    timeout_s=1,
    memory_mb=128,
    max_output_bytes=1000,
)


class Proxy:
    def __init__(self) -> None:
        self.calls: list[Any] = []
        self.timeouts: list[float | None] = []

    def __call__(self, body: Any, *, timeout_s: float | None = None) -> dict[str, Any]:
        self.calls.append(body)
        self.timeouts.append(timeout_s)
        return {"completion": {"text": "answered"}}


@pytest.fixture(autouse=True)
def platform_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LATTICE_LIVE_ANTHROPIC_API_KEY", KEY)
    monkeypatch.setenv("ANTHROPIC_API_KEY", KEY)


def test_a_call_is_relayed_to_the_proxy_and_answered(tmp_path: Path) -> None:
    sandbox, _docker = runner(tmp_path, "ok")
    proxy = Proxy()
    result = sandbox.run_live(REQUEST, proxy)
    assert proxy.calls == [{"messages": []}]
    assert json.loads(result.stdout) == {"id": 1, "completion": {"text": "answered"}}
    assert result.exit_status == 0
    assert result.error is None
    # What is left of the run, and never less than a second: 1 s limit + 0.5 s start-up.
    assert len(proxy.timeouts) == 1
    assert proxy.timeouts[0] is not None and 1.0 <= proxy.timeouts[0] <= 1.5


def test_only_what_the_docker_cli_needs_reaches_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DOCKER_HOST", "tcp://socket-proxy:2375")
    monkeypatch.setenv("HOME", "/home/worker")
    monkeypatch.setenv("LATTICE_DATABASE_URL", "postgresql://secret")
    monkeypatch.setenv("LATTICE_STRIPE_SECRET_KEY", "sk_live_secret")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "secret")
    sandbox, docker = runner(tmp_path, "ok")
    sandbox.run_live(REQUEST, Proxy())
    env = json.loads(docker.with_suffix(".env").read_text())
    assert env["DOCKER_HOST"] == "tcp://socket-proxy:2375"
    assert env["HOME"] == "/home/worker"
    assert "PATH" in env
    assert not any(k.startswith(("LATTICE_", "AWS_")) for k in env)
    assert "secret" not in json.dumps(env)


def test_the_key_is_in_neither_the_arguments_nor_the_environment(tmp_path: Path) -> None:
    sandbox, docker = runner(tmp_path, "ok")
    sandbox.run_live(REQUEST, Proxy())
    argv = json.loads(docker.with_suffix(".argv").read_text())
    env = json.loads(docker.with_suffix(".env").read_text())
    assert not any(KEY in arg for arg in argv)
    assert "--env" not in argv and "-e" not in argv
    assert not any(arg.startswith(("-v", "--volume", "--mount")) for arg in argv)
    assert KEY not in json.dumps(env)
    assert not any(k.startswith(("LATTICE_LIVE_", "ANTHROPIC_")) for k in env)
    # The sandbox is the grading sandbox, unchanged: no network, read-only, no capabilities.
    assert argv[argv.index("--network") + 1] == "none"
    assert "--read-only" in argv
    assert argv[argv.index("--cap-drop") + 1] == "ALL"
    assert argv[-1] == "lattice-sandbox-python:test"
    # Nor in what is streamed in: the archive holds the files and the limits, nothing else.
    assert KEY.encode() not in docker.with_suffix(".tar").read_bytes()


def test_the_archive_holds_the_files_and_limits_but_no_tests() -> None:
    import io
    import tarfile

    with tarfile.open(fileobj=io.BytesIO(build_live_archive(REQUEST))) as tar:
        names = sorted(tar.getnames())
        manifest = json.loads(tar.extractfile("manifest.json").read())  # type: ignore[union-attr]
    assert names == ["manifest.json", "submission/agent.py", "submission/live.py"]
    assert manifest == {"checks": [], "live": {"timeout_s": 1, "max_output_bytes": 1000}}


@pytest.mark.parametrize(
    "scenario", ["wrong-nonce", "skips-an-id", "not-json", "oversized", "unknown-type"]
)
def test_a_frame_off_the_protocol_ends_the_run_without_a_call(
    tmp_path: Path, scenario: str
) -> None:
    sandbox, _ = runner(tmp_path, scenario)
    proxy = Proxy()
    result = sandbox.run_live(REQUEST, proxy)
    assert proxy.calls == []
    assert result.error == "protocol"


def test_a_silent_container_is_stopped_at_its_deadline(tmp_path: Path) -> None:
    sandbox, _ = runner(tmp_path, "silent")
    result = sandbox.run_live(REQUEST, Proxy())
    assert result.timed_out is True
    assert result.duration_ms < 5_000
