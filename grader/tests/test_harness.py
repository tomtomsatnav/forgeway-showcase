"""The harness keeps the nonce out of the environment and the hidden tests off the disk.

Each case runs the real harness in a subprocess, as the sandbox does.
"""

import io
import json
import os
import subprocess
import sys
import tarfile
import textwrap
from pathlib import Path

NONCE = "f00dfeed" * 4

TESTS = textwrap.dedent(
    """
    from lattice_grader.isolation import run_fresh

    import learner


    def fresh_answer():
        import learner
        return learner.answer()


    def test_environment():
        assert learner.nonce_in_environment() is False, "the nonce is in the environment"


    def test_tests_unlinked():
        assert learner.tests_on_disk() == [], "hidden tests are still on disk"


    def test_fresh_process_still_works():
        assert run_fresh(fresh_answer, path=[learner.HERE]) == 42
    """
)

LEARNER = textwrap.dedent(
    f"""
    import os
    from pathlib import Path

    HERE = str(Path(__file__).parent)
    NONCE = "{NONCE}"


    def nonce_in_environment():
        environ = Path("/proc/self/environ")
        raw = environ.read_bytes().decode(errors="replace") if environ.exists() else ""
        return NONCE in raw or any(NONCE in value for value in os.environ.values())


    def tests_on_disk():
        work = Path(HERE).parent
        return sorted(str(p) for p in work.rglob("test_*.py"))


    def answer():
        return 42
    """
)

CHECKS = {
    "environment": "test_learner.py::test_environment",
    "unlinked": "test_learner.py::test_tests_unlinked",
    "fresh": "test_learner.py::test_fresh_process_still_works",
}


def run_harness(tmp_path: Path, stdin_prefix: bytes = NONCE.encode() + b"\n") -> tuple[str, str]:
    archive = io.BytesIO()
    files = {
        "manifest.json": json.dumps({"checks": [{"id": k, "test": v} for k, v in CHECKS.items()]}),
        "submission/learner.py": LEARNER,
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
    env = {"PATH": os.defpath, "LATTICE_WORKDIR": str(work), "PYTHONHASHSEED": "0"}
    done = subprocess.run(
        [sys.executable, "-I", "-m", "lattice_grader.harness"],
        input=stdin_prefix + archive.getvalue(),
        capture_output=True,
        env=env,
        timeout=60,
        check=False,
    )
    return done.stdout.decode().strip(), done.stderr.decode()


def test_the_nonce_arrives_on_stdin_and_the_tests_leave_the_disk(tmp_path: Path) -> None:
    line, stderr = run_harness(tmp_path)
    assert line.startswith(f"LATTICE-REPORT {NONCE} "), stderr[-2000:]
    outcomes = {c["id"]: c for c in json.loads(line.split(" ", 2)[2])["checks"]}
    assert {k: c["outcome"] for k, c in outcomes.items()} == dict.fromkeys(CHECKS, "passed"), (
        outcomes
    )
    assert not (tmp_path / "work" / "tests").exists()


def test_no_nonce_line_means_no_report(tmp_path: Path) -> None:
    line, _ = run_harness(tmp_path, stdin_prefix=b"\n")
    assert "LATTICE-REPORT" not in line
