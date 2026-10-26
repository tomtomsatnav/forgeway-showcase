"""A scaffolded exercise graded for real: its solution passes, its wrong case fails as declared,
and `probe` reports the failing check's message. Needs Docker and the sandbox image."""

import shutil
import subprocess
from pathlib import Path

import pytest

from lattice.application.content_check import check_exercise
from lattice.application.content_probe import ProbeBase, probe_exercise
from lattice.application.content_scaffold import scaffold_exercise
from lattice.domain.grading import GradeStatus
from lattice.infrastructure.content_loader import load_catalogue, read_tree
from lattice.infrastructure.sandbox_docker import DockerSandboxConfig, DockerSandboxRunner
from lattice.settings import get_settings
from tests.content_factory import write_branch, write_exercise

pytestmark = pytest.mark.docker


def _docker_ready() -> bool:
    if shutil.which("docker") is None:
        return False
    image = get_settings().sandbox_image_python
    probe = subprocess.run(["docker", "image", "inspect", image], capture_output=True, check=False)
    return probe.returncode == 0


if not _docker_ready():
    pytest.skip("Docker or the sandbox image is not available", allow_module_level=True)


def test_a_scaffold_grades_for_real_and_probes_report_every_check(tmp_path: Path):
    write_branch(tmp_path, "starter")
    write_exercise(tmp_path, "starter", "one")
    made = scaffold_exercise(tmp_path, load_catalogue(tmp_path), "starter", "shouting")
    source = load_catalogue(tmp_path).sources[made.exercise_id]
    runner = DockerSandboxRunner(
        DockerSandboxConfig(images={"python": get_settings().sandbox_image_python})
    )

    results = check_exercise(source, runner)
    assert [(r.case, r.ok) for r in results] == [("solution", True), ("loses-the-order", True)]

    wrong = read_tree(made.root / "wrong" / "loses-the-order")
    del wrong["expect.yaml"]
    [over_starter] = probe_exercise(source, {"wrong": wrong}, runner)
    [over_solution] = probe_exercise(source, {"none": {}}, runner, base=ProbeBase.SOLUTION)

    assert over_starter.report is not None
    assert over_starter.report.status is GradeStatus.FAILED
    [check] = over_starter.report.checks
    assert check.id == "example" and "original order" in check.message
    assert over_solution.report is not None
    assert over_solution.report.status is GradeStatus.PASSED
