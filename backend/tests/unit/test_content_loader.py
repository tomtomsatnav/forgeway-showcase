from pathlib import Path

import pytest

from lattice.domain.content import ContentError
from lattice.infrastructure.content_loader import load_catalogue
from tests.content_factory import write_branch, write_exercise


def test_valid_content_loads_with_private_assets_kept_off_the_exercise(tmp_path: Path):
    write_branch(tmp_path, "starter")
    write_exercise(tmp_path, "starter", "first-call")

    catalogue = load_catalogue(tmp_path)

    source = catalogue.sources["starter.first-call"]
    assert source.exercise.starter_files.keys() == {"solution_mod.py"}
    assert "test_add.py" in source.tests()
    assert [c.name for c in source.wrong_cases()] == ["subtracts"]
    assert "return a + b" not in source.exercise.model_dump_json()


def test_content_hash_changes_when_any_file_changes(tmp_path: Path):
    write_branch(tmp_path, "starter")
    ex_dir = write_exercise(tmp_path, "starter", "first-call")
    before = load_catalogue(tmp_path).sources["starter.first-call"].exercise.content_hash

    (ex_dir / "tests" / "test_add.py").write_text("def test_adds():\n    assert True\n")

    after = load_catalogue(tmp_path).sources["starter.first-call"].exercise.content_hash
    assert before != after


def test_a_project_branch_and_carry_from_load_from_yaml(tmp_path: Path):
    write_branch(tmp_path, "starter")
    write_branch(tmp_path, "project-x", order=1, requires=["starter"], kind="project")
    write_exercise(tmp_path, "starter", "one")
    write_exercise(tmp_path, "project-x", "ingest")
    write_exercise(
        tmp_path,
        "project-x",
        "serve",
        prerequisites=["project-x.ingest"],
        carry_from="project-x.ingest",
    )

    catalogue = load_catalogue(tmp_path)

    assert catalogue.graph.branches["project-x"].kind == "project"
    assert catalogue.graph.branches["starter"].kind == "standard"
    assert catalogue.sources["project-x.serve"].exercise.carry_from == "project-x.ingest"


def test_errors_name_the_file_and_field(tmp_path: Path):
    write_branch(tmp_path, "starter")
    write_exercise(tmp_path, "starter", "bad-xp", xp=-5)

    with pytest.raises(ContentError) as info:
        load_catalogue(tmp_path)

    assert any("bad-xp/exercise.yaml: xp:" in p for p in info.value.problems)


def test_missing_wrong_case_and_missing_test_function_are_reported(tmp_path: Path):
    write_branch(tmp_path, "starter")
    ex_dir = write_exercise(
        tmp_path,
        "starter",
        "thin",
        checks=[{"id": "adds", "title": "Adds", "test": "test_add.py::test_missing"}],
    )
    for f in (ex_dir / "wrong" / "subtracts").iterdir():
        f.unlink()
    (ex_dir / "wrong" / "subtracts").rmdir()

    with pytest.raises(ContentError) as info:
        load_catalogue(tmp_path)

    problems = "\n".join(info.value.problems)
    assert "test function not found" in problems
    assert "needs at least one wrong" in problems


def test_wrong_case_must_name_a_real_check(tmp_path: Path):
    write_branch(tmp_path, "starter")
    ex_dir = write_exercise(tmp_path, "starter", "first-call")
    (ex_dir / "wrong" / "subtracts" / "expect.yaml").write_text("fails: nonexistent\n")

    with pytest.raises(ContentError, match="unknown check 'nonexistent'"):
        load_catalogue(tmp_path)


def test_flavour_must_reference_real_content(tmp_path: Path):
    from lattice.infrastructure.theme_flavour import load_flavour

    write_branch(tmp_path, "starter")
    write_exercise(tmp_path, "starter", "first-call")
    graph = load_catalogue(tmp_path).graph
    flavour_dir = tmp_path / "themes" / "rpg"
    flavour_dir.mkdir(parents=True)
    (flavour_dir / "flavour.yaml").write_text(
        "quests:\n  starter.first-call: Hello\n  starter.gone: Bye\n"
    )

    with pytest.raises(ContentError, match=r"unknown exercise 'starter\.gone'"):
        load_flavour(tmp_path, "rpg", graph)


BOSS = (
    "{name: The Hoarder, epithet: Keeper of the index, lore: Old and vast., defeat: It crumbles.}"
)


def boss_graph(tmp_path: Path):
    write_branch(tmp_path, "starter", order=0)
    write_branch(tmp_path, "retrieval", order=1, requires=["starter"])
    write_exercise(tmp_path, "starter", "one")
    write_exercise(tmp_path, "retrieval", "chunking")
    write_exercise(
        tmp_path,
        "retrieval",
        "project",
        tier="capstone",
        xp=350,
        prerequisites=["retrieval.chunking"],
    )
    (tmp_path / "themes" / "rpg").mkdir(parents=True)
    return load_catalogue(tmp_path).graph


def write_flavour(tmp_path: Path, text: str) -> None:
    (tmp_path / "themes" / "rpg" / "flavour.yaml").write_text(text)


def test_a_boss_is_keyed_by_a_capstone_exercise(tmp_path: Path):
    from lattice.infrastructure.theme_flavour import load_flavour

    graph = boss_graph(tmp_path)
    write_flavour(tmp_path, f"bosses:\n  retrieval.project: {BOSS}\n")

    boss = load_flavour(tmp_path, "rpg", graph).bosses["retrieval.project"]
    assert (boss.name, boss.epithet, boss.lore, boss.defeat) == (
        "The Hoarder",
        "Keeper of the index",
        "Old and vast.",
        "It crumbles.",
    )


def test_a_boss_must_be_a_capstone_and_unknown_ids_are_rejected(tmp_path: Path):
    from lattice.infrastructure.theme_flavour import load_flavour

    graph = boss_graph(tmp_path)
    write_flavour(
        tmp_path,
        "bosses:\n"
        f"  retrieval.chunking: {BOSS}\n  retrieval.gone: {BOSS}\n  retrieval.project: {BOSS}\n",
    )

    with pytest.raises(ContentError) as info:
        load_flavour(tmp_path, "rpg", graph)
    problems = "\n".join(info.value.problems)
    assert "boss 'retrieval.chunking' is not a capstone exercise" in problems
    assert "boss 'retrieval.gone' is not a capstone exercise" in problems
    assert "retrieval.project" not in problems


def test_a_boss_rejects_extra_and_missing_fields(tmp_path: Path):
    from pydantic import ValidationError

    from lattice.infrastructure.theme_flavour import load_flavour

    graph = boss_graph(tmp_path)
    write_flavour(tmp_path, "bosses:\n  retrieval.project: {name: n, epithet: e, lore: l}\n")
    with pytest.raises(ValidationError, match="defeat"):
        load_flavour(tmp_path, "rpg", graph)
    write_flavour(
        tmp_path,
        "bosses:\n  retrieval.project: {name: n, epithet: e, lore: l, defeat: d, hp: 9}\n",
    )
    with pytest.raises(ValidationError, match="hp"):
        load_flavour(tmp_path, "rpg", graph)


def test_a_capstone_without_a_boss_fails_only_when_bosses_are_required(tmp_path: Path):
    from lattice.infrastructure.theme_flavour import load_flavour

    graph = boss_graph(tmp_path)
    write_flavour(tmp_path, "quests:\n  starter.one: Hello\n")

    assert load_flavour(tmp_path, "rpg", graph).bosses == {}
    with pytest.raises(ContentError, match=r"capstone 'retrieval\.project' has no boss"):
        load_flavour(tmp_path, "rpg", graph, require_bosses=True)
    write_flavour(tmp_path, f"bosses:\n  retrieval.project: {BOSS}\n")
    assert set(load_flavour(tmp_path, "rpg", graph, require_bosses=True).bosses) == {
        "retrieval.project"
    }


def test_a_duplicate_key_in_flavour_is_rejected_not_silently_overwritten(tmp_path: Path):
    from lattice.infrastructure.theme_flavour import load_flavour

    graph = boss_graph(tmp_path)
    write_flavour(
        tmp_path,
        f"bosses:\n  retrieval.project: {BOSS}\nquests: {{}}\n"
        f"bosses:\n  retrieval.project: {BOSS}\n",
    )

    with pytest.raises(ContentError, match=r"duplicate key 'bosses' \(first defined on line 1\)"):
        load_flavour(tmp_path, "rpg", graph)


def test_a_duplicate_key_in_exercise_yaml_is_rejected(tmp_path: Path):
    write_branch(tmp_path, "starter")
    ex_dir = write_exercise(tmp_path, "starter", "first-call")
    meta = ex_dir / "exercise.yaml"
    meta.write_text(meta.read_text() + "xp: 999\n")

    with pytest.raises(ContentError, match="duplicate key 'xp'"):
        load_catalogue(tmp_path)


def test_a_duplicate_key_in_release_front_matter_is_rejected(tmp_path: Path):
    write_branch(tmp_path, "starter")
    write_exercise(tmp_path, "starter", "first-call")
    releases = tmp_path / "releases"
    releases.mkdir()
    (releases / "2026.10.0.md").write_text(
        "---\nversion: 2026.10.0\ndate: 2026-10-01\ntitle: A\ntitle: B\nsummary: S\n---\n\nBody\n"
    )

    with pytest.raises(ContentError, match="duplicate key 'title'"):
        load_catalogue(tmp_path)


def test_the_strict_loader_accepts_equal_keys_in_different_mappings():
    from lattice.infrastructure.yaml_loading import load_yaml

    assert load_yaml("a: {x: 1}\nb: {x: 2}\n") == {"a": {"x": 1}, "b": {"x": 2}}
