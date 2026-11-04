"""Run grading in a locked-down, throwaway Docker container.

The container has no network, a read-only root filesystem, a small size-capped tmpfs for the
work directory, hard memory, CPU, process and wall-clock limits, and `no_new_privs`. It starts as
root with only `CAP_SETUID`, `CAP_SETGID` and `CAP_KILL`, which `lattice_grader.launcher` uses to
run the harness as 10001 and learner code (`isolation: process`) as 10002; neither keeps any
capability (ADR 0009). The nonce and then the files are streamed in on stdin (a first line, then a
tar archive), so nothing on the host is mounted and the nonce is never in the environment. This
runner needs access to a Docker daemon, which is root-equivalent on that host: it is meant for
local development and CI. Production uses a gVisor-backed runner behind the
same `SandboxRunner` port.
"""

from __future__ import annotations

import io
import json
import logging
import os
import queue
import subprocess
import tarfile
import threading
import time
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from typing import IO

from lattice.domain.grading import SandboxRequest, SandboxResult
from lattice.domain.live import LiveSandboxRequest, LiveSandboxResult, Proxy

logger = logging.getLogger(__name__)

MAX_STDOUT_BYTES = 1024 * 1024
MAX_STDERR_BYTES = 64 * 1024
SANDBOX_USER = "0:0"  # the launcher; the harness runs as 10001 and learner code as 10002
SANDBOX_CAPABILITIES = ("SETUID", "SETGID", "KILL")
MAX_RUN_S = 120  # the largest timeout an exercise may declare
STARTUP_ALLOWANCE_S = 10.0  # container start-up, on top of an exercise's time limit
LIVE_PREFIX = "LATTICE-LIVE"
MAX_LIVE_LINE_BYTES = 640 * 1024  # a call frame: the harness caps a request at 512 KB
MAX_LIVE_FRAMES = 500  # far more than any run's call limit, so a flood ends the run
# All the docker CLI reads: its binary path, its config under HOME, DOCKER_HOST and friends, and
# a proxy if its daemon is reached through one. Nothing else of the worker's reaches it.
_DOCKER_ENV_NAMES = frozenset(
    {
        "PATH",
        "HOME",
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "NO_PROXY",
        "http_proxy",
        "https_proxy",
        "no_proxy",
    }
)


def longest_run_s(timeout_factor: float, startup_allowance_s: float = STARTUP_ALLOWANCE_S) -> float:
    """The longest a run can last before the runner kills it: the largest exercise timeout,
    scaled for the runtime, plus start-up."""
    return MAX_RUN_S * timeout_factor + startup_allowance_s


def container_name() -> str:
    """A fresh grading container's name. The production socket-proxy lets the worker kill only
    containers named like this (`deploy/vps/socket-proxy/haproxy.cfg`)."""
    return f"lattice-grade-{uuid.uuid4().hex[:12]}"


@dataclass(frozen=True)
class DockerSandboxConfig:
    images: Mapping[str, str]  # runtime name -> image reference (pin by digest in production)
    docker_binary: str = "docker"
    cpus: float = 1.0
    # A cgroup limit on host tasks. Under gVisor those include the runtime's own threads, about 30
    # before any grading starts, so this is more than the 43 the largest capstone needs.
    pids_limit: int = 128
    workdir_size_mb: int = 32
    startup_allowance_s: float = STARTUP_ALLOWANCE_S
    # The memory ceiling whatever an exercise declares: the VPS runs several sandboxes at once.
    max_memory_mb: int = 768
    # Scales every exercise's wall-clock limit for a slower runtime: gVisor on a small VPS runs the
    # same code several times slower than Docker's default runtime on a laptop. Authors still
    # budget against `timeout_s`; this only keeps a correct solution from timing out in production.
    timeout_factor: float = 1.0
    oci_runtime: str | None = (
        None  # e.g. "runsc": a user-space kernel between learner code and the host
    )


class DockerSandboxRunner:
    """`SandboxRunner` backed by `docker run`."""

    def __init__(self, config: DockerSandboxConfig) -> None:
        self._config = config

    def run(self, request: SandboxRequest) -> SandboxResult:
        image = self._config.images.get(request.runtime)
        if image is None:
            raise ValueError(f"no sandbox image configured for runtime '{request.runtime}'")
        name = container_name()
        command = self._command(name, image, request)
        archive = request.nonce.encode() + b"\n" + build_archive(request)

        started = time.monotonic()
        process = subprocess.Popen(  # noqa: S603 - argv list, no shell
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=docker_env(),
        )
        assert process.stdin and process.stdout and process.stderr  # noqa: S101 - set by PIPE
        stdout = _CappedReader(process.stdout, MAX_STDOUT_BYTES)
        stderr = _CappedReader(process.stderr, MAX_STDERR_BYTES)
        stdout.start()
        stderr.start()
        try:
            process.stdin.write(archive)
            process.stdin.close()
        except BrokenPipeError:
            logger.warning("sandbox closed stdin early", extra={"container": name})

        deadline = self.deadline_s(request)
        timed_out = False
        while process.poll() is None:
            if stdout.overflowed or stderr.overflowed:
                break
            if time.monotonic() - started > deadline:
                timed_out = True
                break
            time.sleep(0.05)
        if process.poll() is None:
            self._kill(name)
            process.wait(timeout=10)
        stdout.join(timeout=5)
        stderr.join(timeout=5)

        return SandboxResult(
            exit_code=process.returncode,
            stdout=stdout.text(),
            stderr=stderr.text(),
            timed_out=timed_out,
            output_truncated=stdout.overflowed or stderr.overflowed,
            duration_ms=int((time.monotonic() - started) * 1000),
        )

    def run_live(self, request: LiveSandboxRequest, proxy: Proxy) -> LiveSandboxResult:
        """Run a live run (ADR 0012): `live.py` over the learner's files, with each model call the
        container asks for answered by `proxy`. The container is the grading sandbox, unchanged:
        no network, no mounts, nothing in its environment or arguments but the image. Its stdin
        stays open as the channel's return path, and every line it writes is checked here."""
        image = self._config.images.get(request.runtime)
        if image is None:
            raise ValueError(f"no sandbox image configured for runtime '{request.runtime}'")
        name = container_name()
        archive = build_live_archive(request)
        started = time.monotonic()
        process = subprocess.Popen(  # noqa: S603 - argv list, no shell
            self._command(name, image, request),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=docker_env(),
        )
        assert process.stdin and process.stdout and process.stderr  # noqa: S101 - set by PIPE
        stderr = _CappedReader(process.stderr, MAX_STDERR_BYTES)
        stderr.start()
        lines: queue.Queue[bytes | None] = queue.Queue()
        threading.Thread(target=_read_lines, args=(process.stdout, lines), daemon=True).start()
        deadline = (
            started
            + request.timeout_s * self._config.timeout_factor
            + (self._config.startup_allowance_s)
        )
        result: LiveSandboxResult | None = None
        try:
            process.stdin.write(f"{request.nonce} live {len(archive)}\n".encode() + archive)
            process.stdin.flush()
            result = self._relay(request, proxy, process.stdin, lines, deadline)
        except (BrokenPipeError, OSError):
            logger.warning("live sandbox closed its channel", extra={"container": name})
        finally:
            if process.poll() is None:
                self._kill(name)
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
            stderr.join(timeout=5)
        duration_ms = int((time.monotonic() - started) * 1000)
        if result is None:
            result = LiveSandboxResult(
                exit_status=None, stdout="", stderr="",
                timed_out=time.monotonic() >= deadline, error="no-report",
            )  # fmt: skip
        return replace(result, duration_ms=duration_ms, container_stderr=stderr.text())

    def _relay(
        self,
        request: LiveSandboxRequest,
        proxy: Proxy,
        stdin: IO[bytes],
        lines: queue.Queue[bytes | None],
        deadline: float,
    ) -> LiveSandboxResult | None:
        """Serve the container's call frames until its report. Anything off-protocol ends it."""
        prefix = f"{LIVE_PREFIX} {request.nonce} ".encode()
        expected = 1
        for _ in range(MAX_LIVE_FRAMES):
            try:
                line = lines.get(timeout=max(deadline - time.monotonic(), 0.001))
            except queue.Empty:
                return LiveSandboxResult(None, "", "", timed_out=True, error="no-report")
            if line is None:
                return None
            message = _frame(line, prefix)
            if message is None:
                return LiveSandboxResult(None, "", "", error="protocol")
            if message.get("type") == "done":
                return _done(message)
            call_id, body = message.get("id"), message.get("request")
            if message.get("type") != "call" or call_id != expected or not isinstance(body, dict):
                return LiveSandboxResult(None, "", "", error="protocol")
            expected += 1
            # At least a second, so a call made at the deadline can fail cleanly.
            left = max(deadline - time.monotonic(), 1.0)
            reply = {"id": call_id, **proxy(body, timeout_s=left)}
            stdin.write(json.dumps(reply, separators=(",", ":")).encode() + b"\n")
            stdin.flush()
        return LiveSandboxResult(None, "", "", error="protocol")

    def reap_orphans(self) -> int:
        """Kill grading containers left behind by a crashed worker.

        A live run never outlasts the longest exercise timeout plus the startup allowance, so
        any grading container older than that has lost its worker.
        """
        listing = subprocess.run(  # noqa: S603 - argv list, no shell
            [self._config.docker_binary, "ps", "-q", "--filter", "label=lattice.role=grader"],
            capture_output=True, text=True, check=False, timeout=15,
        )  # fmt: skip
        ids = listing.stdout.split()
        if not ids:
            return 0
        inspect = subprocess.run(  # noqa: S603 - argv list, no shell
            [self._config.docker_binary, "inspect", "-f", "{{.Name}} {{.Created}}", *ids],
            capture_output=True, text=True, check=False, timeout=15,
        )  # fmt: skip
        cutoff = datetime.now(UTC) - timedelta(
            seconds=longest_run_s(self._config.timeout_factor, self._config.startup_allowance_s)
        )
        reaped = 0
        for line in inspect.stdout.splitlines():
            name, created = line.strip().lstrip("/").split(" ", 1)
            if datetime.fromisoformat(created[:26].rstrip("Z") + "+00:00") < cutoff:
                self._kill(name)
                reaped += 1
        if reaped:
            logger.warning("reaped orphaned grading containers", extra={"status": reaped})
        return reaped

    def deadline_s(self, request: SandboxRequest) -> float:
        """Seconds a run may take: the exercise's limit, scaled for the runtime, plus start-up."""
        return request.timeout_s * self._config.timeout_factor + self._config.startup_allowance_s

    def _command(
        self, name: str, image: str, request: SandboxRequest | LiveSandboxRequest
    ) -> list[str]:
        c = self._config
        memory = f"{min(request.memory_mb, c.max_memory_mb)}m"
        return [
            c.docker_binary, "run", "--rm", "-i",
            "--name", name,
            "--network", "none",
            "--read-only",
            "--tmpfs", f"/work:rw,nosuid,nodev,noexec,size={c.workdir_size_mb}m,mode=1777",
            "--tmpfs", "/tmp:rw,nosuid,nodev,noexec,size=8m,mode=1777",  # noqa: S108
            # Root with three capabilities, only so `lattice_grader.launcher` can start the harness
            # as 10001 and learner code as 10002 (and kill it); both keep no capability, and
            # no_new_privs stops any exec from regaining one.
            "--user", SANDBOX_USER,
            "--cap-drop", "ALL",
            *(arg for cap in SANDBOX_CAPABILITIES for arg in ("--cap-add", cap)),
            "--security-opt", "no-new-privileges",
            "--memory", memory,
            "--memory-swap", memory,
            "--cpus", str(c.cpus),
            "--pids-limit", str(c.pids_limit),
            "--ulimit", "nofile=256:256",
            "--ulimit", "fsize=16777216:16777216",
            "--label", "lattice.role=grader",
            *(["--runtime", c.oci_runtime] if c.oci_runtime else []),
            image,
        ]  # fmt: skip

    def _kill(self, name: str) -> None:
        subprocess.run(  # noqa: S603 - argv list, no shell
            [self._config.docker_binary, "kill", name],
            capture_output=True,
            check=False,
            timeout=15,
        )


def build_archive(request: SandboxRequest) -> bytes:
    """Tar archive holding the manifest, the learner's submission and the hidden tests."""
    buffer = io.BytesIO()
    manifest: dict[str, object] = {
        "checks": [{"id": cid, "test": test} for cid, test in request.checks.items()]
    }
    if request.isolation != "inprocess":
        manifest["isolation"] = request.isolation
    with tarfile.open(fileobj=buffer, mode="w") as tar:
        _add(tar, "manifest.json", json.dumps(manifest))
        for path, text in request.submission.items():
            _add(tar, f"submission/{path}", text)
        for path, text in request.tests.items():
            _add(tar, f"tests/{path}", text)
    return buffer.getvalue()


def build_live_archive(request: LiveSandboxRequest) -> bytes:
    """Tar archive for a live run: a manifest of its limits and the files. No tests."""
    buffer = io.BytesIO()
    manifest = {
        "checks": [],
        "live": {"timeout_s": request.timeout_s, "max_output_bytes": request.max_output_bytes},
    }
    with tarfile.open(fileobj=buffer, mode="w") as tar:
        _add(tar, "manifest.json", json.dumps(manifest))
        for path, text in request.files.items():
            _add(tar, f"submission/{path}", text)
    return buffer.getvalue()


def docker_env() -> dict[str, str]:
    """An allow-list of the worker's environment for the docker CLI. Docker passes a container
    nothing of the CLI's environment unless asked (`--env`, which is never used), so this is belt
    and braces: no `LATTICE_*` secret is even in the process that starts a sandbox."""
    return {
        k: v for k, v in os.environ.items() if k in _DOCKER_ENV_NAMES or k.startswith("DOCKER_")
    }


def _frame(line: bytes, prefix: bytes) -> dict[str, object] | None:
    """A container line as a message, or None if it is not one of ours."""
    if len(line) > MAX_LIVE_LINE_BYTES or not line.startswith(prefix):
        return None
    try:
        message = json.loads(line[len(prefix) :])
    except ValueError:
        return None
    return message if isinstance(message, dict) else None


def _done(message: dict[str, object]) -> LiveSandboxResult:
    def text(key: str) -> str:
        value = message.get(key)
        return value if isinstance(value, str) else ""

    status = message.get("exit_status")
    error = message.get("error")
    return LiveSandboxResult(
        exit_status=status if type(status) is int else None,
        stdout=text("stdout"),
        stderr=text("stderr"),
        stdout_truncated=message.get("stdout_truncated") is True,
        stderr_truncated=message.get("stderr_truncated") is True,
        timed_out=message.get("timed_out") is True,
        error=error if isinstance(error, str) else None,
    )


def _read_lines(stream: IO[bytes], lines: queue.Queue[bytes | None]) -> None:
    """Hand the container's lines over one by one; an overlong line ends the stream."""
    while True:
        line = stream.readline(MAX_LIVE_LINE_BYTES + 1)
        if not line or len(line) > MAX_LIVE_LINE_BYTES:
            lines.put(line or None)
            if line:
                lines.put(None)
            return
        lines.put(line)


def _add(tar: tarfile.TarFile, name: str, text: str) -> None:
    data = text.encode()
    info = tarfile.TarInfo(name)
    info.size = len(data)
    info.mode = 0o644
    tar.addfile(info, io.BytesIO(data))


class _CappedReader(threading.Thread):
    """Drain a pipe on a thread, keeping at most `limit` bytes."""

    def __init__(self, stream: IO[bytes], limit: int) -> None:
        super().__init__(daemon=True)
        self._stream = stream
        self._limit = limit
        self._chunks: list[bytes] = []
        self._size = 0
        self.overflowed = False

    def run(self) -> None:
        while chunk := self._stream.read1(65536):  # type: ignore[attr-defined]
            if self._size + len(chunk) > self._limit:
                self._chunks.append(chunk[: self._limit - self._size])
                self._size = self._limit
                self.overflowed = True
                return
            self._chunks.append(chunk)
            self._size += len(chunk)

    def text(self) -> str:
        return b"".join(self._chunks).decode("utf-8", errors="replace")
