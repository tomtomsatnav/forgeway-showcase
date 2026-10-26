"""Run a function in a fresh Python process, for checks that mean "after a restart".

A restart in the test's own process can be faked: learner code can stash state on `sys`, in
`builtins`, on another module or in `os.environ`, and reloading its module does not clear any of
that. `run_fresh` calls a module-level function in a new interpreter instead, so the only things
that cross are the JSON arguments going in and the JSON result coming out.

    def session(data, now):            # module level, in the test file
        import memory                  # imported afresh in the child
        ...
        return {"tickets": [...], "data": data}

    result = run_fresh(session, data, now, path=[submission_dir])

The child is started like `python -I` (no user site directory, no script directory on the path)
but with an environment built from scratch rather than ignored, so the hash seed stays fixed and
grading stays deterministic. It runs the interpreter itself (never a file in the sandbox's noexec
work directory) and is one extra process, well inside the sandbox's pids limit. Whatever the
function prints goes to stderr: the result travels on a private copy of stdout. Each call starts
in a new, empty working directory of its own, so a file one session writes beside itself is not
there for the next. Test modules import pytest for their marks, which mean nothing outside a
pytest run, and importing pytest is about half of a session's start-up, so the child puts a
stand-in in `sys.modules`: `pytest.mark.<name>(...)` leaves a function as it is, and any other
attribute imports the real pytest and returns its own. The child refuses `lattice_grader`
imports from the same files as the parent (`lattice_grader.guard`) before it loads anything
else.

The harness deletes the hidden tests from disk after collection, so the child cannot load the
test file from its path. The harness hands their source to `remember_sources` first, and the
child is sent that source (compiled under the original file name) instead.

When this process serves a submission through the bridge (`isolation: process`, ADR 0009), so
does the child: a `path` entry that is a bridged submission is not put on the child's `sys.path`
but served by a bridge of the child's own. The function still runs in the fresh interpreter, and
the learner code it imports runs in a process of its own beneath it, so learner code cannot
reach the function's frames or the fakes it builds there either.
"""

from __future__ import annotations

import inspect
import json
import os
import subprocess
import sys
import tempfile
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from lattice_grader import bridge, guard, launcher

DEFAULT_TIMEOUT = 20.0
MAX_STDERR = 4000
_SOURCES: dict[str, str] = {}  # resolved test file path -> its source, kept by the harness


def remember_sources(sources: dict[str, str]) -> None:
    """Keep test files' source in memory, so `run_fresh` works after the files are deleted."""
    _SOURCES.update(sources)


_BOOTSTRAP = r"""
import importlib.util, json, os, sys, traceback
request = json.loads(sys.stdin.read())
out = os.fdopen(os.dup(1), "w", encoding="utf-8")
os.dup2(2, 1)
if request["guard"]:
    from lattice_grader import guard
    guard.install(request["guard"])
sys.path[:0] = request["path"]
class _Marks:
    def __getattr__(self, name):
        def mark(*args, **kwargs):
            if len(args) == 1 and callable(args[0]) and not kwargs:
                return args[0]
            return lambda function: function
        return mark
class _LazyPytest(type(sys)):
    def __getattr__(self, name):
        if name == "mark":
            return _Marks()
        real = sys.modules.get("pytest")
        if real is None or real is self:
            sys.modules.pop("pytest", None)
            real = importlib.import_module("pytest")
        return getattr(real, name)
sys.modules.setdefault("pytest", _LazyPytest("pytest"))
bridges = []
if request["bridge"]:
    from pathlib import Path
    from lattice_grader import bridge
    bridges = [bridge.install(Path(root)) for root in request["bridge"]]
try:
    if request["source"] is None:
        spec = importlib.util.spec_from_file_location("_fresh_entry", request["file"])
        module = importlib.util.module_from_spec(spec)
        sys.modules["_fresh_entry"] = module
        spec.loader.exec_module(module)
    else:
        import types
        module = types.ModuleType("_fresh_entry")
        module.__file__ = request["file"]
        sys.modules["_fresh_entry"] = module
        exec(compile(request["source"], request["file"], "exec"), module.__dict__)
    function = module
    for name in request["name"].split("."):
        function = getattr(function, name)
    reply = {"result": function(*request["args"])}
    text = json.dumps(reply)
except BaseException as exc:
    frames = traceback.extract_tb(exc.__traceback__)
    where = [f"{f.filename}:{f.lineno} in {f.name}" for f in frames[-3:]]
    learner = exc.__dict__.get("__learner_frames__") if hasattr(exc, "__dict__") else None
    if learner:
        where = [line.strip() for line in learner[-3:]]
    text = json.dumps({"error": f"{type(exc).__name__}: {exc}", "where": where})
out.write(text)
out.flush()
for opened in bridges:
    opened.close()
"""


class FreshProcessError(Exception):
    """The function failed in the fresh process: it raised, timed out or returned non-JSON."""


def run_fresh(
    function: Callable[..., Any],
    *args: Any,
    path: Sequence[str | os.PathLike[str]] = (),
    cwd: str | os.PathLike[str] | None = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> Any:
    """Call `function(*args)` in a new interpreter and return its result as plain JSON values.

    `function` must be defined at module level in a file; the child loads that file afresh and
    calls it. `args` and the result must be JSON-serialisable. `path` is put at the front of the
    child's `sys.path` (the learner's submission directory, usually), so it is importable from
    anywhere. `cwd` is the child's working directory; by default each call gets a new, empty
    temporary directory, removed when the child exits, so nothing written relative to the working
    directory survives into the next call.
    """
    file = inspect.getsourcefile(function) or function.__code__.co_filename
    if not file or file.startswith("<") or "<" in function.__qualname__:
        raise TypeError("run_fresh needs a function defined at module level in a file")
    resolved = str(Path(file).resolve())
    roots = [Path(p).resolve() for p in path]
    bridged = set(bridge.installed_roots())
    request = {
        "file": resolved,
        "source": _SOURCES.get(resolved),
        "name": function.__qualname__,
        "path": [str(root) for root in roots if root not in bridged],
        "bridge": [str(root) for root in roots if root in bridged],
        "args": json.loads(json.dumps(list(args))),
        "guard": list(guard.guarded_roots()),
    }
    env = {
        "PATH": os.defpath,
        "PYTHONHASHSEED": "0",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONIOENCODING": "utf-8",
    }
    if launcher.available():
        # The child's own bridge asks the same launcher to start learner code as the second user.
        env[launcher.SOCKET_ENV] = os.environ[launcher.SOCKET_ENV]
    try:
        with tempfile.TemporaryDirectory(
            prefix="lattice-fresh-", ignore_cleanup_errors=True
        ) as scratch:
            if launcher.available():
                # Learner code beneath the session runs as the second user, in this directory.
                Path(scratch).chmod(0o777)  # a fresh, empty working directory
            done = subprocess.run(  # noqa: S603 - argv list, no shell
                [sys.executable, "-s", "-P", "-c", _BOOTSTRAP],
                input=json.dumps(request),
                capture_output=True,
                text=True,
                encoding="utf-8",
                env=env,
                cwd=cwd if cwd is not None else scratch,
                timeout=timeout,
                check=False,
            )
    except subprocess.TimeoutExpired as exc:
        raise FreshProcessError(
            f"{function.__name__} did not finish within {timeout:g} seconds in a fresh process"
        ) from exc
    try:
        reply = json.loads(done.stdout)
    except ValueError:
        tail = done.stderr[-MAX_STDERR:].strip()
        raise FreshProcessError(
            f"the fresh process for {function.__name__} exited with status {done.returncode} "
            f"and no result. Its stderr ends:\n{tail}"
        ) from None
    if "error" in reply:
        where = "; ".join(reply["where"])
        raise FreshProcessError(f"in a fresh process: {reply['error']} (at {where})")
    return reply["result"]
