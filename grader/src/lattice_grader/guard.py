"""Refuse imports of `lattice_grader` from learner code.

Hidden tests import the grader's reference implementations, so the package is installed in the
sandbox; without this guard a submission could borrow the taught behaviour in one line.
`install(roots)` hooks the three ways an import starts, `sys.meta_path` (a module loaded for the
first time), `builtins.__import__` (every `import` statement, including one for a module a test
has already loaded) and `importlib.import_module`, and each asks who is importing.

The importer is found by walking the stack outwards from the import. Frames in the standard
library, in installed packages other than this one, and in generated code (`<string>`,
`<frozen importlib._bootstrap>`) are passed over, so routing the import through `importlib` or
`exec` changes nothing. The first frame left decides: a file under a guarded root (the learner's
submission) is refused, anything else (hidden tests, the grader itself) is allowed.

This is a guard against borrowing, not an adversarial boundary (ADR 0003): code in the same
process can unhook it, find an already-loaded module in `sys.modules`, or compile code under a
false file name. The harness also rejects any submission whose text names `lattice_grader`.
"""

from __future__ import annotations

import builtins
import importlib
import os
import sys
import sysconfig
from collections.abc import Callable, Iterable, Mapping, Sequence
from importlib.machinery import ModuleSpec
from pathlib import Path
from types import FrameType, ModuleType

PACKAGE = "lattice_grader"
MESSAGE = f"{PACKAGE} is the grader's own code; your solution must not import it."

_HERE = Path(__file__).resolve()
_LIBRARY_DIRS = tuple(
    {Path(p).resolve() for key, p in sysconfig.get_paths().items() if key.endswith("lib")}
)
_roots: list[Path] = []


def install(roots: Iterable[str | os.PathLike[str]]) -> None:
    """Refuse `lattice_grader` imports from files under `roots`. Safe to call more than once."""
    for root in roots:
        resolved = Path(root).resolve()
        if resolved not in _roots:
            _roots.append(resolved)
    if not any(isinstance(finder, _Finder) for finder in sys.meta_path):
        sys.meta_path.insert(0, _Finder())
    if not isinstance(builtins.__import__, _GuardedImport):
        builtins.__import__ = _GuardedImport(builtins.__import__)
    if not isinstance(importlib.import_module, _GuardedImportModule):
        importlib.import_module = _GuardedImportModule(importlib.import_module)


def guarded_roots() -> tuple[str, ...]:
    """The roots guarded in this process, for passing on to a child interpreter."""
    return tuple(str(root) for root in _roots)


def _is_grader(name: str) -> bool:
    return name == PACKAGE or name.startswith(PACKAGE + ".")


def _refuse_if_learner(name: str) -> None:
    if not _roots or not _is_grader(name):
        return
    frame: FrameType | None = sys._getframe()  # this module's own frames are passed over
    while frame is not None:
        code_file = frame.f_code.co_filename
        frame = frame.f_back
        if code_file.startswith("<"):
            continue  # generated code: exec, eval, the frozen import machinery
        file = Path(code_file).resolve()
        if file == _HERE:
            continue
        if any(file.is_relative_to(root) for root in _roots):
            raise ImportError(MESSAGE, name=name)
        if file.is_relative_to(_HERE.parent) or not any(
            file.is_relative_to(library) for library in _LIBRARY_DIRS
        ):
            return  # the grader itself, or a hidden test


class _Finder:
    """Consulted only for modules not yet in `sys.modules`; it never finds anything itself."""

    def find_spec(
        self, fullname: str, path: Sequence[str] | None, target: ModuleType | None = None
    ) -> ModuleSpec | None:
        _refuse_if_learner(fullname)
        return None


class _GuardedImport:
    def __init__(self, original: Callable[..., ModuleType]) -> None:
        self._original = original

    def __call__(
        self,
        name: str,
        globals: Mapping[str, object] | None = None,  # noqa: A002 - mirrors __import__
        locals: Mapping[str, object] | None = None,  # noqa: A002
        fromlist: Sequence[str] | None = (),
        level: int = 0,
    ) -> ModuleType:
        if level == 0:
            _refuse_if_learner(name)
        return self._original(name, globals, locals, fromlist, level)


class _GuardedImportModule:
    def __init__(self, original: Callable[..., ModuleType]) -> None:
        self._original = original

    def __call__(self, name: str, package: str | None = None) -> ModuleType:
        if not name.startswith("."):
            _refuse_if_learner(name)
        return self._original(name, package)
