import re
from pathlib import Path
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

from lattice import cli
from lattice.application import content_check
from lattice.application.content_probe import ProbeBase, probe_exercise
from lattice.domain.grading import GradeStatus
from lattice.infrastructure.content_loader import ExerciseSource, load_catalogue
from tests.content_factory import write_branch, write_exercise
from tests.fakes import ScriptedRunner

SOLVED = {"solution_mod.py": "def add(a, b):\n    return a + b\n"}
BROKEN = {"solution_mod.py": "def add(a, b):\n    return a - b\n"}


@pytest.fixture
def content(tmp_path: Path) -> Path:
    write_branch(tmp_path, "starter")
    write_exercise(
        tmp_path,
        "starter",
        "adder",
        checks=[
            {"id": "adds", "title": "Adds numbers", "test": "test_add.py::test_adds"},
            {"id": "also", "title": "Adds again", "test": "test_add.py::test_adds"},
        ],
    )
    return tmp_path


@pytest.fixture
def source(content: Path) -> ExerciseSource:
    return load_catalogue(content).sources["starter.adder"]


def test_probes_are_laid_over_the_starter_and_report_every_check(source: ExerciseSource):
    runner = ScriptedRunner()
    results = probe_exercise(source, {"good": SOLVED, "bad": BROKEN}, runner)

    assert [r.name for r in results] == ["good", "bad"]
    good, bad = (r.report for r in results)
    assert good is not None and good.status is GradeStatus.PASSED
    assert bad is not None and bad.status is GradeStatus.FAILED
    assert [(c.id, c.passed, c.message) for c in bad.checks] == [
        ("adds", False, "nope"),
        ("also", False, "nope"),
    ]
    assert runner.requests[1].submission == BROKEN


def test_a_probe_over_the_solution_keeps_the_files_it_does_not_replace(source: ExerciseSource):
    runner = ScriptedRunner()
    [result] = probe_exercise(source, {"empty": {}}, runner, base=ProbeBase.SOLUTION)

    assert result.report is not None and result.report.status is GradeStatus.PASSED
    assert runner.requests[0].submission == SOLVED


def test_a_probe_with_files_the_learner_cannot_edit_is_refused(source: ExerciseSource):
    [result] = probe_exercise(source, {"sneaky": {"conftest.py": ""}}, ScriptedRunner())
    assert result.report is None
    assert result.refused is not None and "conftest.py" in result.refused


def _probe(content: Path, monkeypatch: pytest.MonkeyPatch, *args: str) -> tuple[int, str]:
    monkeypatch.setattr(cli, "_sandbox_runner", ScriptedRunner)
    result = CliRunner().invoke(
        cli.app, ["content", "probe", "starter.adder", *args, "--content-dir", str(content)]
    )
    return result.exit_code, result.output


def test_the_cli_grades_a_wrong_case_directory_and_prints_every_check(
    content: Path, monkeypatch: pytest.MonkeyPatch
):
    wrong = content / "branches/starter/exercises/adder/wrong/subtracts"
    solution = content / "branches/starter/exercises/adder/solution"

    code, output = _probe(content, monkeypatch, str(wrong), str(solution))

    assert code == 0, output
    assert f"{wrong} (over the starter): failed" in output
    assert "✗ adds: Adds numbers" in output and "✗ also: Adds again" in output
    assert output.count("      nope") == 2
    assert f"{solution} (over the starter): passed" in output


def test_the_cli_fails_when_a_probe_cannot_be_graded(
    content: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    probe = tmp_path / "probe"
    probe.mkdir()
    (probe / "helper.py").write_text("")

    code, output = _probe(content, monkeypatch, str(probe), "--base", "solution")

    assert code == 1
    assert "not graded" in output and "helper.py" in output
    code, output = _probe(content, monkeypatch, str(probe), "--base", "nowhere")
    assert code != 0


def test_content_test_prints_each_case_s_time_on_request(
    content: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(cli, "_sandbox_runner", ScriptedRunner)
    command = ["content", "test", "--only", "starter.adder", "--content-dir", str(content)]

    plain = CliRunner().invoke(cli.app, command)
    timed = CliRunner().invoke(cli.app, [*command, "--time"])

    assert plain.exit_code == timed.exit_code == 1  # the scripted runner says "nope"
    assert "✓ starter.adder [solution]\n" in plain.output and " s\n" not in plain.output
    assert re.search(r"✓ starter\.adder \[solution\] \d+\.\d s\n", timed.output)
    assert re.search(r"✗ starter\.adder \[subtracts\] \d+\.\d s\n", timed.output)
    assert "budget" not in timed.output


def test_content_test_flags_a_solution_over_the_budget(
    content: Path, monkeypatch: pytest.MonkeyPatch
):
    clock = iter(range(0, 1000, 20))  # every case takes 20 s
    monkeypatch.setattr(cli, "_sandbox_runner", ScriptedRunner)
    monkeypatch.setattr(content_check, "time", SimpleNamespace(perf_counter=lambda: next(clock)))
    command = ["content", "test", "--only", "starter.adder", "--time", "--content-dir"]

    result = CliRunner().invoke(cli.app, [*command, str(content)])

    assert "✓ starter.adder [solution] 20.0 s" in result.output
    assert result.output.count("over the 15 s budget") == 1
