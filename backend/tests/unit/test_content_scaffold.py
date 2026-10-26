import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest
import yaml
from typer.testing import CliRunner

from lattice.application.content_review import ReviewInput, Status, review_exercise
from lattice.cli import app
from lattice.domain.content import Isolation
from lattice.infrastructure.content_loader import load_catalogue
from tests.content_factory import write_branch, write_exercise

runner = CliRunner()


@pytest.fixture
def content(tmp_path: Path) -> Path:
    write_branch(tmp_path, "starter")
    write_exercise(tmp_path, "starter", "one")
    write_branch(tmp_path, "rag", order=1, requires=["starter"])
    write_exercise(tmp_path, "rag", "chunks")
    write_exercise(
        tmp_path,
        "rag",
        "service",
        tier="capstone",
        xp=300,
        prerequisites=["rag.chunks"],
        editable=["solution_mod.py"],
    )
    return tmp_path


def _new(content: Path, *args: str) -> tuple[int, str]:
    result = runner.invoke(app, ["content", "new", *args, "--content-dir", str(content)])
    return result.exit_code, result.output


def _validate(content: Path) -> tuple[int, str]:
    result = runner.invoke(
        app, ["content", "validate", "--require-capstones", "--content-dir", str(content)]
    )
    return result.exit_code, result.output


def _load(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _run_example_test(ex_dir: Path, module: str, learner_dir: Path) -> None:
    """Run the scaffold's own check against the learner files in `learner_dir`, in process."""
    try:
        _load(module, learner_dir / f"{module}.py")
        tests = _load(f"test_{module}", ex_dir / "tests" / f"test_{module}.py")
        tests.test_example()
    finally:
        sys.modules.pop(module, None)
        sys.modules.pop(f"test_{module}", None)


def test_a_scaffold_validates_and_joins_the_branch_capstone(content: Path):
    code, output = _new(content, "rag", "re-rank", "--title", "Re-ranking by hand")
    assert code == 0, output
    assert "capstone 'rag.service'" in output

    code, output = _validate(content)
    assert code == 0, output
    catalogue = load_catalogue(content)
    exercise = catalogue.sources["rag.re-rank"].exercise
    assert exercise.title == "Re-ranking by hand"
    assert exercise.editable == ("re_rank.py",)
    assert exercise.isolation is Isolation.PROCESS
    assert "rag.re-rank" in catalogue.sources["rag.service"].exercise.prerequisites
    assert [c.name for c in catalogue.sources["rag.re-rank"].wrong_cases()] == ["loses-the-order"]


def test_the_scaffold_solution_passes_its_check_and_the_wrong_case_fails_it(content: Path):
    _new(content, "rag", "re-rank")
    ex_dir = content / "branches" / "rag" / "exercises" / "re-rank"

    _run_example_test(ex_dir, "re_rank", ex_dir / "solution")
    with pytest.raises(AssertionError) as failed:
        _run_example_test(ex_dir, "re_rank", ex_dir / "wrong" / "loses-the-order")
    expect = yaml.safe_load((ex_dir / "wrong" / "loses-the-order" / "expect.yaml").read_text())
    assert expect["message_contains"] in str(failed.value)


def test_the_scaffold_passes_its_own_cheat_review(content: Path):
    _new(content, "rag", "re-rank")
    source = load_catalogue(content).sources["rag.re-rank"]
    items = review_exercise(ReviewInput(source.exercise, source.tests(), source.wrong_cases()))
    assert [i.title for i in items if i.status is Status.WARN] == []


def test_scaffolding_refuses_to_overwrite(content: Path):
    _new(content, "rag", "re-rank")
    brief = content / "branches" / "rag" / "exercises" / "re-rank" / "brief.md"
    brief.write_text("# My edits\n")

    code, output = _new(content, "rag", "re-rank")

    assert code == 1
    assert "refusing to overwrite" in output
    assert brief.read_text() == "# My edits\n"
    capstone = yaml.safe_load(
        (content / "branches/rag/exercises/service/exercise.yaml").read_text()
    )
    assert capstone["prerequisites"].count("rag.re-rank") == 1


def test_bad_requests_are_refused_without_writing(content: Path):
    assert _new(content, "nowhere", "x")[0] == 1
    assert _new(content, "rag", "Not_A_Slug")[0] == 1
    code, output = _new(content, "rag", "second", "--tier", "capstone")
    assert code == 1 and "already has a capstone" in output
    code, output = _new(content, "starter", "big", "--tier", "capstone")
    assert code == 1 and "requires nothing" in output
    code, output = _new(content, "rag", "next", "--carry-from", "chunks")
    assert code == 1 and "project branches" in output
    assert sorted(p.name for p in (content / "branches/rag/exercises").iterdir()) == [
        "chunks",
        "service",
    ]


def test_a_capstone_scaffold_depends_on_the_whole_branch(tmp_path: Path):
    write_branch(tmp_path, "starter")
    write_exercise(tmp_path, "starter", "one")
    write_branch(tmp_path, "rag", order=1, requires=["starter"])
    write_exercise(tmp_path, "rag", "a")
    write_exercise(tmp_path, "rag", "b", prerequisites=["rag.a"])
    write_exercise(tmp_path, "rag", "c")

    code, output = _new(tmp_path, "rag", "finale", "--tier", "capstone")

    assert code == 0, output
    assert _validate(tmp_path)[0] == 0
    exercise = load_catalogue(tmp_path).sources["rag.finale"].exercise
    assert sorted(exercise.prerequisites) == ["rag.b", "rag.c"]
    assert exercise.xp == 300 and exercise.limits.timeout_s == 60


def test_a_project_milestone_starts_from_the_previous_reference_solution(tmp_path: Path):
    write_branch(tmp_path, "starter")
    write_exercise(tmp_path, "starter", "one")
    write_branch(tmp_path, "proj", order=1, requires=["starter"], kind="project")
    write_exercise(tmp_path, "proj", "ingest")
    write_exercise(
        tmp_path, "proj", "release", tier="capstone", xp=300, prerequisites=["proj.ingest"]
    )

    code, output = _new(tmp_path, "proj", "serve", "--carry-from", "ingest")

    assert code == 0, output
    assert _validate(tmp_path)[0] == 0
    source = load_catalogue(tmp_path).sources["proj.serve"]
    assert source.exercise.carry_from == "proj.ingest"
    assert source.exercise.prerequisites == ("proj.ingest",)
    assert source.exercise.editable == ("solution_mod.py", "serve.py")
    assert source.exercise.starter_files["solution_mod.py"] == (
        "def add(a, b):\n    return a + b\n"
    )
    assert set(source.solution()) == {"solution_mod.py", "serve.py"}
