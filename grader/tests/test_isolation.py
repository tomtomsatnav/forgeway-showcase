"""`run_fresh` gives a real restart: nothing stashed in the parent, or in an earlier child,
survives into the next call."""

import builtins
import importlib.util
import json
import os
import sys
import textwrap
from collections.abc import Iterator
from pathlib import Path

import pytest

from lattice_grader.isolation import FreshProcessError, run_fresh

LEARNER = textwrap.dedent(
    """
    import builtins, json, os, sys

    def stash(value):
        sys.__dict__["_stash"] = value
        builtins._stash = value
        json._stash = value
        os.environ["STASH"] = value

    def found():
        return {
            "sys": sys.__dict__.get("_stash"),
            "builtins": getattr(builtins, "_stash", None),
            "module": getattr(json, "_stash", None),
            "environ": os.environ.get("STASH"),
        }
    """
)
NOTHING = {"sys": None, "builtins": None, "module": None, "environ": None}


@pytest.fixture
def submission(tmp_path: Path) -> Path:
    (tmp_path / "learner.py").write_text(LEARNER)
    return tmp_path


# Entry points the child loads from this file. They import the learner's module afresh.
def stash_then_find(value):
    import learner

    learner.stash(value)
    return learner.found()


def find():
    import learner

    return learner.found()


def echo(*args):
    return {"args": list(args), "hash": hash("fixed seed"), "path0": sys.path[0]}


def noisy():
    print("learner chatter on stdout")
    print("and on stderr", file=sys.stderr)
    return "result"


def explode():
    import learner  # noqa: F401

    raise ValueError("bad preference")


def not_json():
    return {1, 2}


def hang():
    import time

    time.sleep(30)


def test_a_stash_does_not_survive_into_the_next_process(submission: Path) -> None:
    stashed = run_fresh(stash_then_find, "secret", path=[submission])
    assert stashed == dict.fromkeys(NOTHING, "secret")
    assert run_fresh(find, path=[submission]) == NOTHING


def test_a_stash_in_the_parent_does_not_reach_the_child(submission: Path) -> None:
    sys.path.insert(0, str(submission))
    try:
        import learner

        learner.stash("parent")
        assert learner.found() == dict.fromkeys(NOTHING, "parent")
        assert run_fresh(find, path=[submission]) == NOTHING
    finally:
        sys.path.remove(str(submission))
        sys.modules.pop("learner", None)
        sys.__dict__.pop("_stash", None)
        builtins.__dict__.pop("_stash", None)
        json.__dict__.pop("_stash", None)
        os.environ.pop("STASH", None)


def test_arguments_and_results_cross_as_json(submission: Path) -> None:
    got = run_fresh(echo, {"a": [1, 2.5, None]}, "x", path=[submission])
    assert got["args"] == [{"a": [1, 2.5, None]}, "x"]
    assert got["path0"] == str(submission.resolve())
    again = run_fresh(echo, path=[submission])
    assert again["hash"] == got["hash"], "The hash seed is fixed, so grading is deterministic."


def test_output_on_stdout_does_not_corrupt_the_result() -> None:
    assert run_fresh(noisy) == "result"


def test_failures_are_reported(submission: Path) -> None:
    with pytest.raises(FreshProcessError, match="ValueError: bad preference"):
        run_fresh(explode, path=[submission])
    with pytest.raises(FreshProcessError, match="TypeError"):
        run_fresh(not_json)
    with pytest.raises(FreshProcessError, match="did not finish"):
        run_fresh(hang, timeout=1)


MARKED = textwrap.dedent(
    """
    import sys

    import pytest


    @pytest.mark.parametrize("seed", [1, 2])
    @pytest.mark.filterwarnings("ignore")
    def session(seed=0):
        before = "_pytest" in sys.modules
        with pytest.raises(ValueError):
            raise ValueError("raised")
        return {"before": before, "after": "_pytest" in sys.modules}
    """
)


def test_the_child_imports_pytest_only_when_a_session_uses_it(tmp_path: Path) -> None:
    path = tmp_path / "marked_tests.py"
    path.write_text(MARKED)
    spec = importlib.util.spec_from_file_location("marked_tests", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert run_fresh(module.session) == {"before": False, "after": True}


def test_only_module_level_functions_can_run() -> None:
    def local():
        return 1

    with pytest.raises(TypeError, match="module level"):
        run_fresh(local)


def leave_side_file():
    import learner  # importable from the submission, wherever the child starts

    Path("side.txt").write_text("stashed")
    return {"cwd": str(Path.cwd()), "learner": learner.__file__}


def read_side_file():
    side = Path("side.txt")
    return side.read_text() if side.exists() else None


def test_each_call_starts_in_its_own_empty_directory(submission: Path) -> None:
    first = run_fresh(leave_side_file, path=[submission])
    assert first["learner"] == str(submission.resolve() / "learner.py")
    assert Path(first["cwd"]).resolve() != Path.cwd().resolve()
    assert not Path(first["cwd"]).exists(), "The directory is removed when the child exits."
    assert not (Path.cwd() / "side.txt").exists()
    assert run_fresh(read_side_file) is None, "A side file must not survive into the next call."


def test_an_explicit_cwd_is_used_and_kept(submission: Path, tmp_path: Path) -> None:
    shared = tmp_path / "shared"
    shared.mkdir()
    run_fresh(leave_side_file, path=[submission], cwd=shared)
    assert run_fresh(read_side_file, cwd=shared) == "stashed"


# ---- with the bridge (isolation: process) -------------------------------------------------

PEEKER = textwrap.dedent(
    """
    import os, sys

    def where():
        return {"pid": os.getpid(), "entry": "_fresh_entry" in sys.modules}

    def peek():
        frame, seen = sys._getframe(), []
        while frame is not None:
            seen.extend(frame.f_locals)
            frame = frame.f_back
        return seen

    def fail():
        raise ValueError("bad preference")
    """
)


def bridged_session():
    import peeker

    secret = "the answer"  # noqa: F841 - what learner code must not find in this frame
    return {"fresh": os.getpid(), "learner": peeker.where(), "seen": peeker.peek()}


def bridged_failure():
    import peeker

    peeker.fail()


@pytest.fixture
def bridged(tmp_path: Path) -> Iterator[Path]:
    from lattice_grader import bridge

    (tmp_path / "peeker.py").write_text(PEEKER)
    installed = bridge.install(tmp_path, timeout=3)
    try:
        yield tmp_path
    finally:
        bridge.uninstall(installed)


def test_a_bridged_submission_runs_beneath_the_fresh_process(bridged: Path) -> None:
    got = run_fresh(bridged_session, path=[bridged])
    assert got["learner"]["pid"] != got["fresh"], "Learner code runs in a process of its own."
    assert not got["learner"]["entry"], "The entry file is not loaded beside learner code."
    assert "secret" not in got["seen"], "The session's frames are out of learner code's reach."


def test_a_bridged_failure_names_the_learner_file(bridged: Path) -> None:
    with pytest.raises(FreshProcessError, match=r"ValueError: bad preference \(at peeker.py"):
        run_fresh(bridged_failure, path=[bridged])


def test_an_unbridged_path_is_still_put_on_the_childs_path(submission: Path, bridged: Path) -> None:
    assert run_fresh(find, path=[submission]) == NOTHING
