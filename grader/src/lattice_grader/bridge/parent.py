"""The parent's side of the bridge: start the child, and make `import ask` return a proxy.

`install(submission)` puts a finder at the end of `sys.meta_path`. A test's `import store`
(or `from store import VectorStore`) then finds no module on the parent's own path, the
submission is not on it, and gets a `ProxyModule` instead: every attribute read, write and
delete on it is a request to the child, which imported the real module. The child starts at the
first such import.

In the sandbox the child runs as a second user (10002), started by `lattice_grader.launcher`,
so it can read neither the hidden tests nor the grader package, and cannot signal or inspect the
parent. Outside it (tests of the bridge itself, or a sandbox started without root) the child
runs as the same user. Either way the parent marks itself non-dumpable (Linux
`PR_SET_DUMPABLE`), so a child running as the same user cannot ptrace it or open its
`/proc/<pid>/mem`, `environ` or `fd/*`.
"""

from __future__ import annotations

import ctypes
import importlib.abc
import importlib.machinery
import os
import signal
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path
from types import ModuleType
from typing import Any

from lattice_grader import launcher
from lattice_grader.bridge.peer import Channel, Peer, PeerTimeout, ProtocolError

DEFAULT_TIMEOUT = 10.0
PR_SET_DUMPABLE = 4
_LOCAL_ATTRIBUTES = frozenset(
    {"__name__", "__loader__", "__package__", "__spec__", "__path__", "__file__", "__cached__",
     "__builtins__", "__doc__"}
)  # fmt: skip


class LearnerProcessError(BaseException):
    """Learner code's process timed out, died or broke the protocol.

    A `BaseException`, so a test's `pytest.raises(Exception)` or `except Exception` cannot take
    a dead child for the error it expected. pytest still fails the test with it, and
    `ReportPlugin` shows its message as written, as it does for a test's own assertion.
    """


class Bridge:
    """The child process and the parent's `Peer` for it, started on first use."""

    def __init__(self, submission: Path, *, timeout: float = DEFAULT_TIMEOUT) -> None:
        self.submission = submission.resolve()
        self.timeout = timeout
        self._process: subprocess.Popen[bytes] | launcher.LaunchedProcess | None = None
        self._peer: Peer | None = None
        self._served: set[str] = set()  # learner modules the tests have imported

    @property
    def peer(self) -> Peer:
        if self._peer is None:
            self._peer = self._start()
        return self._peer

    def import_module(self, name: str) -> Any:
        """The child's module `name`. A module served before and since dropped from
        `sys.modules` (a test importing it afresh) runs afresh in the child too: with every
        other dropped one, or with every learner module once the tests hold none."""
        forget: list[str] = []
        if name in self._served:
            held = {n for n in self._served if isinstance(sys.modules.get(n), ProxyModule)}
            forget = sorted(self._served - held) if held else ["*"]
            # Forgotten modules start again: importing one of them next is a first import.
            self._served = held
        self._served.add(name)
        return self.peer.request("import", name=name, args=[forget] if forget else [])

    def close(self) -> None:
        process = self._process
        if process is None:
            return
        if process.stdin is not None:
            process.stdin.close()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        if self._peer is not None:
            self._peer.wait_closed(timeout=2)
        if process.stdout is not None:
            process.stdout.close()

    def _start(self) -> Peer:
        source = Path(__file__).with_name("peer.py").read_text(encoding="utf-8")
        program = f"{source}\nrun_child({{'root': {str(self.submission)!r}}})\n"
        env = {
            "PATH": os.defpath,
            "PYTHONHASHSEED": "0",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONIOENCODING": "utf-8",
        }
        argv = [sys.executable, "-s", "-P", "-c", program]
        if launcher.available():
            # The sandbox started as root: learner code runs as a second user (ADR 0009).
            self._process = launcher.launch(argv, env=env, cwd=str(Path.cwd()))
        else:
            self._process = subprocess.Popen(  # noqa: S603 - argv list, no shell
                argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, env=env, close_fds=True
            )
        assert self._process.stdin and self._process.stdout  # noqa: S101 - set by PIPE
        channel = Channel(self._process.stdout.fileno(), self._process.stdin.fileno())
        return Peer(
            channel,
            guarded=True,
            timeout=self.timeout,
            on_output=_print,
            on_broken=self._broken,
        )

    def _broken(self, exc: Exception) -> BaseException:
        """The learner-facing failure for a child that stopped answering, died or misbehaved."""
        process = self._process
        if isinstance(exc, PeerTimeout):
            message = (
                f"Your code did not finish within {self.timeout:g} seconds, so the grader stopped "
                "it. Look for an infinite loop, or a call that waits for something that never "
                "comes."
            )
        elif isinstance(exc, ProtocolError):
            message = (
                f"Your code's process sent the grader {exc}, so the grader stopped it. Your code "
                "should talk to the tests only by returning values."
            )
        else:
            status = None
            if process is not None:
                try:
                    status = process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    status = None
            if status is not None and status < 0:
                name = signal.Signals(-status).name
                message = (
                    f"Your code's process was killed by {name}; it may have used too much memory."
                )
            elif status is not None:
                message = (
                    f"Your code's process exited with status {status} before it returned. Does "
                    "it call sys.exit() or os._exit()?"
                )
            else:
                message = "Your code's process closed its connection to the grader."
        if process is not None and process.poll() is None:
            process.kill()
            process.wait()
        error = LearnerProcessError(message)
        later = LearnerProcessError(f"Your code's process stopped earlier in this run. {message}")
        # The first call to notice reports what happened; every later call reports it as past.
        if self._peer is not None:
            self._peer.broken = later
        return error


def _print(text: str) -> None:
    sys.stdout.write(text)


class ProxyModule(ModuleType):
    """A learner module seen from the parent: attributes live in the child's real module."""

    def __init__(self, name: str, target: Any) -> None:
        super().__init__(name)
        object.__setattr__(self, "_bridge_target", target)

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_bridge_"):
            raise AttributeError(name)
        return getattr(object.__getattribute__(self, "_bridge_target"), name)

    def __setattr__(self, name: str, value: Any) -> None:
        if name in _LOCAL_ATTRIBUTES:
            object.__setattr__(self, name, value)
        else:
            setattr(object.__getattribute__(self, "_bridge_target"), name, value)

    def __delattr__(self, name: str) -> None:
        if name in _LOCAL_ATTRIBUTES:
            object.__delattr__(self, name)
        else:
            delattr(object.__getattribute__(self, "_bridge_target"), name)


class _Loader(importlib.abc.Loader):
    def __init__(self, bridge: Bridge) -> None:
        self._bridge = bridge

    def create_module(self, spec: importlib.machinery.ModuleSpec) -> ModuleType:
        return ProxyModule(spec.name, self._bridge.import_module(spec.name))

    def exec_module(self, module: ModuleType) -> None:
        return None  # the child ran the module when it was imported


class _Finder(importlib.abc.MetaPathFinder):
    """Finds learner modules, last: only names nothing on the parent's own path provides."""

    def __init__(self, bridge: Bridge) -> None:
        self._bridge = bridge
        self._loader = _Loader(bridge)

    def find_spec(
        self, fullname: str, path: Sequence[str] | None, target: ModuleType | None = None
    ) -> importlib.machinery.ModuleSpec | None:
        root = self._bridge.submission
        relative = Path(*fullname.split("."))
        package = root / relative
        file = root / relative.with_suffix(".py")
        if package.is_dir():
            init = package / "__init__.py"
            origin = str(init) if init.is_file() else None
            spec = importlib.machinery.ModuleSpec(
                fullname, self._loader, origin=origin, is_package=True
            )
            spec.submodule_search_locations = []
        elif file.is_file():
            spec = importlib.machinery.ModuleSpec(fullname, self._loader, origin=str(file))
        else:
            return None
        spec.has_location = spec.origin is not None
        return spec


_installed: list[Bridge] = []


def install(submission: Path, *, timeout: float = DEFAULT_TIMEOUT) -> Bridge:
    """Serve learner modules from a child process. Returns the bridge, to `close()` at the end."""
    _make_undumpable()
    bridge = Bridge(submission, timeout=timeout)
    sys.meta_path.append(_Finder(bridge))
    _installed.append(bridge)
    return bridge


def installed_roots() -> tuple[Path, ...]:
    """The submission directories this process serves through a bridge, for `run_fresh`."""
    return tuple(bridge.submission for bridge in _installed)


def uninstall(bridge: Bridge) -> None:
    """Stop the child and remove the finder (for tests of the bridge itself)."""
    bridge.close()
    sys.meta_path[:] = [
        f for f in sys.meta_path if not (isinstance(f, _Finder) and f._bridge is bridge)
    ]
    for name, module in list(sys.modules.items()):
        loader = getattr(module, "__loader__", None)
        if isinstance(loader, _Loader) and loader._bridge is bridge:
            del sys.modules[name]
    if bridge in _installed:
        _installed.remove(bridge)


def _make_undumpable() -> None:
    if sys.platform == "linux":
        ctypes.CDLL(None, use_errno=True).prctl(PR_SET_DUMPABLE, 0, 0, 0, 0)
