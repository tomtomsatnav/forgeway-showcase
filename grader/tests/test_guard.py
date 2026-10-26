"""Learner code cannot import `lattice_grader`; hidden tests and the grader still can.

Each case runs the real harness in a subprocess, as the sandbox does, so the guard is installed
the way it is in production and never in this test process.
"""

import io
import json
import os
import subprocess
import sys
import tarfile
import textwrap
from pathlib import Path

import pytest

from lattice_grader.guard import MESSAGE

GRADER = "lattice" + "_grader"  # spelt in two parts where it stands for learner text

TESTS = textwrap.dedent(
    """
    import sys
    from pathlib import Path

    from lattice_grader.isolation import FreshProcessError, run_fresh
    from lattice_grader.report import clip

    import learner


    def fresh_session():
        import learner

        return learner.answer()


    def test_answer():
        assert learner.answer() == 42, "answer() should return 42"


    def test_fresh():
        try:
            got = run_fresh(fresh_session, path=[Path(learner.__file__).parent])
        except FreshProcessError as exc:
            raise AssertionError(str(exc)) from None
        assert got == 42, "answer() should return 42 after a restart"


    def test_child_script():
        import subprocess

        done = subprocess.run(
            [sys.executable, "-c", "import learner; print(learner.answer())"],
            cwd=Path(learner.__file__).parent, capture_output=True, text=True, check=False,
        )
        assert done.stdout.strip() == "42", done.stderr.strip().splitlines()[-1]
    """
)
CHECKS = {"answer": "test_learner.py::test_answer", "fresh": "test_learner.py::test_fresh"}

HONEST = "def answer():\n    return 42\n"
# Ways to reach the grader without naming it in one piece. Each must fail with the guard's message.
BORROWS = {
    "import_module": """
import importlib
report = importlib.import_module("lattice" "_grader.report")
def answer():
    return 42
""",
    "dunder_import": """
def answer():
    __import__("lattice" "_grader.report")  # already loaded by the hidden tests
    return 42
""",
    "exec": """
def answer():
    exec("import lattice" "_grader.report as r")
    return 42
""",
    "find_spec": """
import importlib.util
def answer():
    importlib.util.find_spec("lattice" "_grader.memory_reference")
    return 42
""",
}


def grade(tmp_path: Path, learner: str, checks: dict[str, str] = CHECKS) -> dict[str, dict]:
    archive = io.BytesIO()
    files = {
        "manifest.json": json.dumps({"checks": [{"id": k, "test": v} for k, v in checks.items()]}),
        "submission/learner.py": learner,
        "tests/test_learner.py": TESTS,
    }
    with tarfile.open(fileobj=archive, mode="w") as tar:
        for name, text in files.items():
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
    }
    done = subprocess.run(
        [sys.executable, "-I", "-m", "lattice_grader.harness"],
        input=b"n0nce\n" + archive.getvalue(),
        capture_output=True,
        env=env,
        timeout=60,
        check=False,
    )
    line = done.stdout.decode().strip()
    assert line.startswith("LATTICE-REPORT n0nce "), done.stderr.decode()[-2000:]
    return {c["id"]: c for c in json.loads(line.split(" ", 2)[2])["checks"]}


def test_an_honest_submission_passes_and_tests_import_the_grader(tmp_path: Path) -> None:
    checks = {**CHECKS, "child": "test_learner.py::test_child_script"}
    outcomes = grade(tmp_path, HONEST, checks)
    assert {k: c["outcome"] for k, c in outcomes.items()} == dict.fromkeys(checks, "passed")


@pytest.mark.parametrize("route", sorted(BORROWS))
def test_learner_code_cannot_import_the_grader(tmp_path: Path, route: str) -> None:
    outcomes = grade(tmp_path, BORROWS[route])
    for check in outcomes.values():
        assert check["outcome"] == "failed"
        assert MESSAGE in check["message"], check["message"]


def test_a_fresh_process_keeps_the_guard(tmp_path: Path) -> None:
    learner = """
import os
def answer():
    if os.environ.get("NOT_SET") is None and __name__ == "learner":
        import importlib, sys
        if "_fresh_entry" in sys.modules:  # only in the run_fresh child
            importlib.import_module("lattice" "_grader.report")
    return 42
"""
    outcomes = grade(tmp_path, learner)
    assert outcomes["answer"]["outcome"] == "passed"
    assert outcomes["fresh"]["outcome"] == "failed"
    assert MESSAGE in outcomes["fresh"]["message"], outcomes["fresh"]["message"]


def test_naming_the_grader_fails_every_check_without_running(tmp_path: Path) -> None:
    learner = f"# I promise not to use {GRADER}\n" + HONEST
    outcomes = grade(tmp_path, learner)
    for check in outcomes.values():
        assert check["outcome"] == "failed"
        assert MESSAGE in check["message"]
        assert "learner.py" in check["message"]
