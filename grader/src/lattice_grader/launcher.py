"""Sandbox entrypoint: ``python -m lattice_grader.launcher``. Runs learner code as a second user.

The container starts as root with only `CAP_SETUID`, `CAP_SETGID` and `CAP_KILL`, and
`no_new_privs` set. This process stays root, does no grading itself and reads nothing the
learner sends. It:

1. listens on a Unix socket (`SOCKET`) that only processes running as the harness's user
   (`HARNESS_UID`, 10001) may use, checked with `SO_PEERCRED`;
2. starts the harness (`lattice_grader.harness`) as 10001, with the container's stdin, stdout and
   stderr, and steps off the report channel itself;
3. starts each bridge child (ADR 0009) the harness, or a `run_fresh` session beneath it, asks for,
   as `LEARNER_UID` (10002), on pipes the asker passes over the socket, and reports its exit
   status back on that connection; it kills the child when asked or when the connection closes;
4. reaps every process (it is PID 1), and when the harness exits, kills whatever is left and exits
   with the harness's status.

Every process it starts drops its supplementary groups and sets all three of its user and group
ids, so it keeps no capability, and `no_new_privs` means no exec can give one back. Learner code
therefore runs as a user that can read neither the hidden tests (`tests/` is 0700, owned by
10001) nor the grader package (0750, root:10001), cannot open `/proc/<pid>/` of any grader
process, and cannot signal one.

If the container was started as any other user (an older runner), the launcher becomes the
harness in place, and the bridge runs learner code as the same user, as before.
"""

from __future__ import annotations

import contextlib
import json
import os
import pwd
import selectors
import signal
import socket
import struct
import subprocess
import sys
import threading
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import IO, Any

SOCKET_ENV = "LATTICE_LAUNCHER"
SOCKET = "/tmp/lattice-launcher.sock"  # noqa: S108 - a fixed path in the sandbox's private /tmp
HARNESS_UID = 10001
LEARNER_UID = 10002
HARNESS = ("-I", "-m", "lattice_grader.harness")
MAX_REQUEST_BYTES = 1024 * 1024
REQUEST_TIMEOUT_S = 5.0
_UCRED = struct.Struct("3i")  # pid, uid, gid
LINUX_ONLY = "the launcher's side runs in the Linux sandbox only"


def available() -> bool:
    """Whether a launcher serves this process (the sandbox was started as root)."""
    return bool(os.environ.get(SOCKET_ENV))


# The asker's side --------------------------------------------------------------------------------


class LaunchedProcess:
    """A process the launcher started for us: the parts of `subprocess.Popen` the bridge uses.

    The launcher is its parent, so its exit status arrives over the connection, and killing it
    is a request (we run as another user, so we may not signal it ourselves).
    """

    def __init__(
        self, connection: socket.socket, pid: int, stdin: IO[bytes], stdout: IO[bytes]
    ) -> None:
        self._connection = connection
        self.pid = pid
        self.stdin: IO[bytes] | None = stdin
        self.stdout: IO[bytes] | None = stdout
        self.args = ["<launched>"]
        self.returncode: int | None = None
        self._buffer = b""
        self._lock = threading.Lock()

    def poll(self) -> int | None:
        with self._lock:
            if self.returncode is None:
                self._read(blocking=False, timeout=None)
            return self.returncode

    def wait(self, timeout: float | None = None) -> int:
        with self._lock:
            if self.returncode is None:
                self._read(blocking=True, timeout=timeout)
            if self.returncode is None:
                raise subprocess.TimeoutExpired(self.args, timeout or 0)
            return self.returncode

    def kill(self) -> None:
        with contextlib.suppress(OSError):
            self._connection.sendall(b"kill\n")

    def _read(self, *, blocking: bool, timeout: float | None) -> None:
        self._connection.setblocking(blocking)
        if blocking:
            self._connection.settimeout(timeout)
        try:
            while b"\n" not in self._buffer:
                chunk = self._connection.recv(4096)
                if not chunk:  # the launcher went away: treat the child as killed
                    self.returncode = -signal.SIGKILL
                    return
                self._buffer += chunk
        except (BlockingIOError, TimeoutError):
            return
        line, _, self._buffer = self._buffer.partition(b"\n")
        self.returncode = int(json.loads(line)["status"])
        self._connection.close()


def launch(argv: Sequence[str], *, env: Mapping[str, str], cwd: str) -> LaunchedProcess:
    """Start `argv` as the learner's user, with pipes for its stdin and stdout and our stderr.

    `argv[0]` must be this interpreter: the launcher starts nothing else.
    """
    child_in, our_in = os.pipe()
    our_out, child_out = os.pipe()
    connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        connection.connect(os.environ[SOCKET_ENV])
        body = json.dumps({"argv": list(argv), "env": dict(env), "cwd": cwd}).encode()
        header = len(body).to_bytes(4, "big")
        socket.send_fds(connection, [header], [child_in, child_out, 2])
        connection.sendall(body)
        reply = b""
        while b"\n" not in reply:
            chunk = connection.recv(4096)
            if not chunk:
                raise OSError("the launcher refused to start the process")
            reply += chunk
        line, _, rest = reply.partition(b"\n")
        pid = int(json.loads(line)["pid"])
    except BaseException:
        connection.close()
        for fd in (our_in, our_out):
            os.close(fd)
        raise
    finally:
        os.close(child_in)
        os.close(child_out)
    process = LaunchedProcess(connection, pid, os.fdopen(our_in, "wb"), os.fdopen(our_out, "rb"))
    process._buffer = rest
    return process


# The launcher's side -----------------------------------------------------------------------------


def _spawn(
    argv: Sequence[str],
    *,
    uid: int,
    env: Mapping[str, str],
    cwd: str,
    fds: Sequence[int] | None,
) -> int:
    """Fork and exec `argv` as `uid` (and the same gid), with no supplementary groups."""
    pid = os.fork()
    if pid == 0:  # pragma: no cover - runs in the child, which execs or exits
        try:
            if fds is not None:
                for target, fd in enumerate(fds):
                    os.dup2(fd, target)
            os.closerange(3, os.sysconf("SC_OPEN_MAX"))
            _become(uid)
            os.chdir(cwd)
            os.execve(argv[0], list(argv), dict(env))  # noqa: S606 - no shell, by design
        finally:
            os._exit(127)
    return pid


def _become(uid: int) -> None:
    """Drop supplementary groups and set every user and group id: all capabilities go with root."""
    if sys.platform == "linux":
        os.setgroups([])
        os.setresgid(uid, uid, uid)
        os.setresuid(uid, uid, uid)
    else:
        raise OSError(LINUX_ONLY)


def _peer_uid(connection: socket.socket) -> int:
    """The user id of the process at the other end of a Unix socket."""
    if sys.platform == "linux":
        credentials = connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, _UCRED.size)
        return int(_UCRED.unpack(credentials)[1])
    else:  # each branch is a platform check, which mypy skips on the other platform
        raise OSError(LINUX_ONLY)


def _status(wait_status: int) -> int:
    """`waitpid`'s status as `Popen.returncode` reports it: the exit code, or minus the signal."""
    if os.WIFSIGNALED(wait_status):
        return -os.WTERMSIG(wait_status)
    return os.waitstatus_to_exitcode(wait_status)


class _Launcher:
    def __init__(self, server: socket.socket, harness_pid: int) -> None:
        self._server = server
        self._harness = harness_pid
        self._children: dict[int, socket.socket] = {}  # bridge child pid -> its asker
        self._selector = selectors.DefaultSelector()
        self.exit_status: int | None = None

    def serve(self, wakeup: int) -> int:
        self._selector.register(self._server, selectors.EVENT_READ, "accept")
        self._selector.register(wakeup, selectors.EVENT_READ, "reap")
        while True:
            for key, _ in self._selector.select():
                if key.data == "accept":
                    self._accept()
                elif key.data == "reap":
                    with contextlib.suppress(BlockingIOError):
                        os.read(wakeup, 512)
                    self._reap()
                else:
                    self._command(key.fileobj, int(key.data))  # type: ignore[arg-type]
                if self.exit_status is not None:
                    break
            status = self.exit_status
            if status is not None:
                break
        # The harness is done: nothing it started may outlive it.
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.kill(-1, signal.SIGKILL)
        return status

    def _accept(self) -> None:
        try:
            connection, _ = self._server.accept()
        except BlockingIOError:
            return
        try:
            uid = _peer_uid(connection)
            if uid != HARNESS_UID:
                raise PermissionError(f"uid {uid} may not launch processes")
            pid = self._start(connection)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            print(f"launcher: refused a request: {exc}", file=sys.stderr, flush=True)
            connection.close()
            return
        connection.setblocking(False)
        self._children[pid] = connection
        self._selector.register(connection, selectors.EVENT_READ, str(pid))

    def _start(self, connection: socket.socket) -> int:
        connection.settimeout(REQUEST_TIMEOUT_S)
        header, fds, _, _ = socket.recv_fds(connection, 4, 3)
        try:
            if len(fds) != 3:
                raise ValueError("a request passes exactly three descriptors")
            while len(header) < 4:
                more = connection.recv(4 - len(header))
                if not more:
                    raise ValueError("the request ended early")
                header += more
            size = int.from_bytes(header, "big")
            if size > MAX_REQUEST_BYTES:
                raise ValueError("the request is too large")
            body = b""
            while len(body) < size:
                more = connection.recv(min(65536, size - len(body)))
                if not more:
                    raise ValueError("the request ended early")
                body += more
            request: dict[str, Any] = json.loads(body)
            argv = [str(arg) for arg in request["argv"]]
            if not argv or argv[0] != sys.executable:
                raise ValueError("only the Python interpreter may be launched")
            env = {str(k): str(v) for k, v in dict(request["env"]).items()}
            pid = _spawn(argv, uid=LEARNER_UID, env=env, cwd=str(request["cwd"]), fds=fds)
        finally:
            for fd in fds:
                os.close(fd)
        connection.sendall(json.dumps({"pid": pid}).encode() + b"\n")
        return pid

    def _command(self, connection: socket.socket, pid: int) -> None:
        try:
            data = connection.recv(64)
        except BlockingIOError:
            return
        except OSError:
            data = b""
        # A kill request, or the asker went away (then nobody can talk to the child: stop it).
        if not data or b"kill" in data:
            with contextlib.suppress(ProcessLookupError):
                os.kill(pid, signal.SIGKILL)
        if not data:
            self._selector.unregister(connection)

    def _reap(self) -> None:
        while True:
            try:
                pid, wait_status = os.waitpid(-1, os.WNOHANG)
            except ChildProcessError:
                return
            if pid == 0:
                return
            if pid == self._harness:
                status = _status(wait_status)  # a shell's convention for a killed harness
                self.exit_status = status if status >= 0 else 128 - status
                continue
            connection = self._children.pop(pid, None)  # None: an orphan reparented to us
            if connection is None:
                continue
            with contextlib.suppress(KeyError, ValueError):
                self._selector.unregister(connection)
            with contextlib.suppress(OSError):
                connection.setblocking(True)
                connection.sendall(json.dumps({"status": _status(wait_status)}).encode() + b"\n")
            connection.close()


def _harness_env() -> dict[str, str]:
    env = dict(os.environ)
    env[SOCKET_ENV] = SOCKET
    try:
        env["HOME"] = pwd.getpwuid(HARNESS_UID).pw_dir
    except KeyError:
        env["HOME"] = "/"
    return env


def main() -> int:
    if os.getuid() != 0:
        os.execv(sys.executable, [sys.executable, *HARNESS])  # noqa: S606 - no shell, by design
    Path(SOCKET).unlink(missing_ok=True)
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(SOCKET)
    Path(SOCKET).chmod(0o666)  # anyone may connect; SO_PEERCRED decides who is served
    server.listen(16)
    server.setblocking(False)
    reader, writer = os.pipe()  # not inherited by what we start (Python's default)
    os.set_blocking(reader, False)
    os.set_blocking(writer, False)
    signal.signal(signal.SIGCHLD, lambda *_: None)
    signal.set_wakeup_fd(writer, warn_on_full_buffer=False)

    harness = _spawn(
        [sys.executable, *HARNESS],
        uid=HARNESS_UID,
        env=_harness_env(),
        cwd=str(Path.cwd()),
        fds=None,
    )
    # Step off the report channel and the archive: only the harness reads stdin and writes stdout.
    null = os.open(os.devnull, os.O_RDWR)
    os.dup2(null, 0)
    os.dup2(null, 1)
    os.close(null)
    return _Launcher(server, harness).serve(reader)


if __name__ == "__main__":
    raise SystemExit(main())
