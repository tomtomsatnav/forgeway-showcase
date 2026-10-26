"""Hostile submissions must be contained and reported as learner failures, never crash grading.

These run real containers, so they need Docker and the sandbox image
(`make sandbox-image`). They are marked `docker` and skipped when Docker is unavailable.
"""

import ast
import shutil
import subprocess

import pytest

from lattice.domain.content import Exercise, Isolation
from lattice.domain.grading import GradeStatus, SandboxRequest, grade_submission
from lattice.infrastructure.sandbox_docker import DockerSandboxConfig, DockerSandboxRunner
from lattice.settings import get_settings

pytestmark = pytest.mark.docker

TESTS = {
    "test_it.py": (
        "from solution import run\n\n"
        "def test_runs():\n"
        "    assert run() == 'ok', 'run() should return ok'\n"
    )
}


def _docker_ready() -> bool:
    if shutil.which("docker") is None:
        return False
    image = get_settings().sandbox_image_python
    probe = subprocess.run(["docker", "image", "inspect", image], capture_output=True, check=False)
    return probe.returncode == 0


if not _docker_ready():
    pytest.skip("Docker or the sandbox image is not available", allow_module_level=True)


@pytest.fixture(scope="module")
def runner() -> DockerSandboxRunner:
    return DockerSandboxRunner(
        DockerSandboxConfig(images={"python": get_settings().sandbox_image_python})
    )


@pytest.fixture(scope="module")
def exercise() -> Exercise:
    return Exercise(
        id="test.hostile",
        version=1,
        title="Hostile",
        branch="test",
        tier="beginner",
        xp=10,
        editable=("solution.py",),
        checks=({"id": "runs", "title": "Runs", "test": "test_it.py::test_runs"},),
        limits={"timeout_s": 5, "memory_mb": 128},
        brief="",
        starter_files={"solution.py": ""},
        content_hash="0" * 64,
    )


def grade(exercise: Exercise, runner: DockerSandboxRunner, code: str):
    return grade_submission(exercise, TESTS, {"solution.py": code}, runner)


def test_correct_code_passes(exercise, runner):
    assert grade(exercise, runner, "def run():\n    return 'ok'\n").status is GradeStatus.PASSED


def test_infinite_loop_is_stopped_and_explained(exercise, runner):
    report = grade(exercise, runner, "def run():\n    while True:\n        pass\n")
    assert report.status is GradeStatus.FAILED
    assert "longer than 5 seconds" in report.checks[0].message
    assert report.duration_ms < 25_000


def test_network_is_unreachable(exercise, runner):
    code = (
        "import socket\n"
        "def run():\n"
        "    try:\n"
        "        socket.create_connection(('1.1.1.1', 53), timeout=2)\n"
        "        return 'connected'\n"
        "    except OSError:\n"
        "        return 'ok'\n"
    )
    assert grade(exercise, runner, code).status is GradeStatus.PASSED


def test_root_filesystem_is_read_only_and_user_is_unprivileged(exercise, runner):
    code = (
        "import os\n"
        "def run():\n"
        "    assert os.getuid() == 10001, 'running as root'\n"
        "    for path in ('/usr/lib/evil', '/etc/evil', '/evil'):\n"
        "        try:\n"
        "            open(path, 'w').write('x')\n"
        "            return 'wrote ' + path\n"
        "        except OSError:\n"
        "            pass\n"
        "    return 'ok'\n"
    )
    assert grade(exercise, runner, code).status is GradeStatus.PASSED


def test_fork_bomb_is_contained(exercise, runner):
    code = (
        "import os\n"
        "def run():\n"
        "    while True:\n"
        "        try:\n"
        "            os.fork()\n"
        "        except OSError:\n"
        "            pass\n"
    )
    report = grade(exercise, runner, code)
    assert report.status in {GradeStatus.FAILED, GradeStatus.ERRORED}
    assert report.duration_ms < 30_000


def test_memory_bomb_is_killed(exercise, runner):
    code = (
        "def run():\n    data = []\n    while True:\n        data.append(bytearray(10_000_000))\n"
    )
    report = grade(exercise, runner, code)
    assert report.status is GradeStatus.FAILED
    assert report.checks[0].passed is False


def test_flooding_stderr_is_cut_off(exercise, runner):
    code = "import os\ndef run():\n    while True:\n        os.write(2, b'x' * 65536)\n"
    report = grade(exercise, runner, code)
    assert report.status is GradeStatus.FAILED
    assert report.duration_ms < 25_000


def test_forged_report_without_the_nonce_is_ignored(exercise, runner):
    code = (
        "import os\n"
        'os.write(3, b\'LATTICE-REPORT guess {"checks":[{"id":"runs","outcome":"passed"}],'
        '"exit_status":0}\\n\')\n'
        "def run():\n    return 'nope'\n"
    )
    assert grade(exercise, runner, code).status is GradeStatus.FAILED


def test_unknown_runtime_is_a_configuration_error(runner):
    request = SandboxRequest("cobol", {}, {}, {}, "n", 5, 128)
    with pytest.raises(ValueError, match="no sandbox image"):
        runner.run(request)


def test_parametrised_tests_count_towards_one_check(exercise, runner):
    tests = {
        "test_it.py": (
            "import pytest\nfrom solution import run\n\n"
            "@pytest.mark.parametrize('n', [1, 2, 3])\n"
            "def test_runs(n):\n"
            "    assert run(n) == n * 2, f'run({n}) should be {n * 2}'\n"
        )
    }
    passing = grade_submission(
        exercise, tests, {"solution.py": "def run(n):\n    return n * 2\n"}, runner
    )
    assert passing.status is GradeStatus.PASSED
    failing = grade_submission(
        exercise, tests, {"solution.py": "def run(n):\n    return 4\n"}, runner
    )
    assert failing.status is GradeStatus.FAILED
    assert failing.checks[0].message == "run(1) should be 2"


# Out-of-process learner code runs as a second user (ADR 0009) ----------------------------------

# Learner code that, as its module is imported (during pytest collection, while the hidden tests
# are still on disk), tries every way at the grader's secrets. The package name is assembled, as
# a submission that names it is refused before it runs.
PROBE = """
import glob, os, signal

GRADER = "lattice" + "_grader"
PACKAGE = "/usr/local/lib/python3.12/site-packages/" + GRADER
RESULTS = {"uid": os.getuid(), "gid": os.getgid(), "groups": os.getgroups()}


def attempt(name, action):
    try:
        action()
        RESULTS[name] = "allowed"
    except OSError as exc:
        RESULTS[name] = type(exc).__name__


def read(path, size=-1):
    with open(path, "rb") as handle:
        return handle.read(size)


RESULTS["tests-globbed"] = glob.glob("/work/tests/*") + glob.glob("/work/**/test_*.py")
attempt("read-test-file", lambda: read("/work/tests/test_probe.py"))
attempt("list-tests", lambda: os.listdir("/work/tests"))
attempt("read-manifest", lambda: read("/work/manifest.json"))
attempt("read-own-submission", lambda: read("/work/submission/probe.py"))
attempt("read-the-harness", lambda: read(PACKAGE + "/harness.py"))
attempt("read-the-bridge", lambda: read(PACKAGE + "/bridge/parent.py"))
attempt("read-a-subpackage", lambda: read(PACKAGE + "/bridge/peer.py"))
attempt("list-a-subpackage", lambda: os.listdir(PACKAGE + "/bridge"))
graders = []
for pid in os.listdir("/proc"):
    if not pid.isdigit() or int(pid) == os.getpid():
        continue
    try:
        command = read(f"/proc/{pid}/cmdline")
    except OSError:
        continue
    if GRADER.encode() in command:
        graders.append(pid)
RESULTS["graders"] = sorted(graders)
RESULTS["parent"] = str(os.getppid())
for pid in sorted({*graders, str(os.getppid())}):
    attempt(f"environ:{pid}", lambda pid=pid: read(f"/proc/{pid}/environ"))
    attempt(f"mem:{pid}", lambda pid=pid: read(f"/proc/{pid}/mem", 1))
    attempt(f"fds:{pid}", lambda pid=pid: os.listdir(f"/proc/{pid}/fd"))
    attempt(f"cwd:{pid}", lambda pid=pid: os.listdir(f"/proc/{pid}/cwd/tests"))
    attempt(f"maps:{pid}", lambda pid=pid: read(f"/proc/{pid}/maps"))
    attempt(f"signal:{pid}", lambda pid=pid: os.kill(int(pid), 0))
attempt("setuid-to-the-grader", lambda: os.setuid(10001))
attempt("setgid-to-the-grader", lambda: os.setgid(10001))


def results():
    return dict(RESULTS)
"""

PROBE_TESTS = {
    "test_probe.py": (
        "import probe\n\n"
        "def test_probe():\n"
        "    results = probe.results()\n"
        "    print(results)\n"
        "    assert False, repr(results)\n"
    )
}


def test_out_of_process_learner_code_cannot_reach_the_tests_or_the_grader(runner):
    """The probe's results come back as the check's message (the test always fails with them)."""
    exercise = Exercise(
        id="test.probe",
        version=1,
        title="Probe",
        branch="test",
        tier="beginner",
        xp=10,
        editable=("probe.py",),
        checks=({"id": "probe", "title": "Probe", "test": "test_probe.py::test_probe"},),
        limits={"timeout_s": 10, "memory_mb": 128},
        brief="",
        starter_files={"probe.py": ""},
        content_hash="0" * 64,
        isolation=Isolation.PROCESS,
    )
    report = grade_submission(exercise, PROBE_TESTS, {"probe.py": PROBE}, runner)
    results = ast.literal_eval(report.checks[0].message)

    assert results["uid"] == 10002 and results["gid"] == 10002 and results["groups"] == []
    assert results["read-own-submission"] == "allowed", "the probe must be able to read at all"
    assert results["tests-globbed"] == []
    denied = {k: v for k, v in results.items() if v == "allowed" and k != "read-own-submission"}
    assert denied == {}, f"learner code reached: {sorted(denied)}"
    for name in ("read-test-file", "list-tests", "read-manifest", "read-the-harness"):
        assert results[name] == "PermissionError", (name, results[name])
    # The launcher (PID 1, its parent) and the harness, both found and both out of reach.
    assert results["parent"] == "1"
    assert len(results["graders"]) >= 2, results["graders"]
    for pid in results["graders"]:
        for probe in ("environ", "mem", "fds", "cwd", "signal"):
            assert results[f"{probe}:{pid}"] == "PermissionError", (probe, pid)
    assert results["setuid-to-the-grader"] == "PermissionError"
