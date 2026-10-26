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
import subprocess
import tarfile
import threading
import time
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import IO

from lattice.domain.grading import SandboxRequest, SandboxResult

logger = logging.getLogger(__name__)

MAX_STDOUT_BYTES = 1024 * 1024
MAX_STDERR_BYTES = 64 * 1024
SANDBOX_USER = "0:0"  # the launcher; the harness runs as 10001 and learner code as 10002
SANDBOX_CAPABILITIES = ("SETUID", "SETGID", "KILL")
MAX_RUN_S = 120  # the largest timeout an exercise may declare
STARTUP_ALLOWANCE_S = 10.0  # container start-up, on top of an exercise's time limit


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
    pids_limit: int = 64
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
            command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE
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

    def _command(self, name: str, image: str, request: SandboxRequest) -> list[str]:
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
