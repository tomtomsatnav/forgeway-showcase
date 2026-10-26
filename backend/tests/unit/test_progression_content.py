"""The progression files: parsing, cross-checks against the exercises, and the shipped content."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from lattice.cli import app
from lattice.domain.content import ContentError
from lattice.domain.progression import (
    GENERALIST,
    TalentState,
    can_allocate,
    reference_solution_branches,
)
from lattice.domain.progression.levels import MAX_LEVEL
from lattice.infrastructure.content_loader import load_catalogue
from lattice.infrastructure.theme_flavour import load_flavour
from tests.content_factory import write_branch, write_exercise

REAL_CONTENT = Path(__file__).parents[3] / "content"


@pytest.fixture
def content(tmp_path: Path) -> Path:
    write_branch(tmp_path, "starter", order=0)
    write_branch(tmp_path, "retrieval", order=1, requires=["starter"])
    write_exercise(tmp_path, "starter", "one")
    write_exercise(tmp_path, "retrieval", "chunking")
    return tmp_path


def write_progression(root: Path, *, classes="paths: []", talents="nodes: []", badges="badges: []"):
    (root / "progression").mkdir(exist_ok=True)
    (root / "progression" / "classes.yaml").write_text(classes)
    (root / "progression" / "talents.yaml").write_text(talents)
    (root / "progression" / "badges.yaml").write_text(badges)


def test_content_without_a_progression_directory_is_generalist_only(content):
    progression = load_catalogue(content).progression
    assert progression.tree.path_ids == (GENERALIST,)
    assert progression.badges == ()


def test_progression_files_load(content):
    write_progression(
        content,
        classes="paths:\n  - {id: retrieval, title: R, summary: s, home_branch: retrieval}\n",
        talents=(
            "nodes:\n  - id: a\n    title: A\n    summary: s\n    subtree: retrieval\n"
            "    required_exercises: [retrieval.chunking]\n    effects:\n"
            "      - reference_solutions: retrieval\n      - title: Adept\n"
        ),
        badges=(
            "badges:\n  - id: b\n    title: B\n    description: d\n"
            "    criterion: {kind: branch_complete, branch: starter}\n"
        ),
    )
    progression = load_catalogue(content).progression
    assert list(progression.tree.nodes) == ["a"]
    assert [b.id for b in progression.badges] == ["b"]


def test_problems_across_all_three_files_are_collected(content):
    write_progression(
        content,
        classes="paths:\n  - {id: ghost, title: G, summary: s, home_branch: nowhere}\n",
        talents=(
            "nodes:\n  - id: a\n    title: A\n    summary: s\n"
            "    required_exercises: [starter.no]\n"
            "    effects: [{title: T}]\n  - id: b\n    title: B\n    summary: s\n    effects: []\n"
        ),
        badges=(
            "badges:\n  - id: x\n    title: X\n    description: d\n"
            "    criterion: {kind: logged_in, n: 1}\n"
        ),
    )
    with pytest.raises(ContentError) as caught:
        load_catalogue(content)
    text = "\n".join(caught.value.problems)
    assert "talents.yaml: nodes[1].effects" in text
    assert "badges.yaml: badges[0]" in text


def test_cross_reference_problems_are_reported_together(content):
    write_progression(
        content,
        classes="paths:\n  - {id: ghost, title: G, summary: s, home_branch: nowhere}\n",
        talents=(
            "nodes:\n  - id: a\n    title: A\n    summary: s\n"
            "    required_exercises: [starter.no]\n"
            "    effects: [{title: T}]\n"
        ),
        badges=(
            "badges:\n  - id: x\n    title: X\n    description: d\n"
            "    criterion: {kind: branch_complete, branch: nowhere}\n"
        ),
    )
    with pytest.raises(ContentError) as caught:
        load_catalogue(content)
    text = "\n".join(caught.value.problems)
    assert "badge 'x' refers to unknown branch 'nowhere'" in text
    assert "path 'ghost' has unknown home branch 'nowhere'" in text
    assert "talent 'a' requires unknown exercise 'starter.no'" in text


def test_a_missing_file_in_the_progression_directory_is_an_error(content):
    write_progression(content)
    (content / "progression" / "badges.yaml").unlink()
    with pytest.raises(ContentError, match=r"badges\.yaml: missing"):
        load_catalogue(content)


def test_flavour_for_an_unknown_path_is_rejected(content):
    write_progression(content)
    (content / "themes" / "rpg").mkdir(parents=True)
    (content / "themes" / "rpg" / "flavour.yaml").write_text(
        "paths:\n  wizard: {name: Wizard, epithet: e}\n"
    )
    catalogue = load_catalogue(content)
    with pytest.raises(ContentError, match="unknown path 'wizard'"):
        load_flavour(content, "rpg", catalogue.graph, catalogue.progression.tree.path_ids)


# --- the shipped content ----------------------------------------------------------------------


@pytest.fixture(scope="module")
def shipped():
    return load_catalogue(REAL_CONTENT)


def test_shipped_flavour_names_every_path(shipped):
    path_ids = shipped.progression.tree.path_ids
    flavour = load_flavour(REAL_CONTENT, "rpg", shipped.graph, path_ids)
    assert set(flavour.paths) == set(path_ids)


def test_shipped_talents_are_all_reachable_and_affordable(shipped):
    """With everything passed and enough levels, every path can take every one of its talents."""
    tree = shipped.progression.tree
    everything = frozenset(tree.graph.exercises)
    for path in tree.path_ids:
        taken: list[str] = []
        usable = [n for n in tree.nodes.values() if tree.in_subtree(n, path)]
        progressed = True
        while progressed:
            progressed = False
            for node in usable:
                state = TalentState(MAX_LEVEL, path, everything, tuple(taken))
                if node.id not in taken and can_allocate(tree, node.id, state).allowed:
                    taken.append(node.id)
                    progressed = True
        assert sorted(taken) == sorted(n.id for n in usable), path


def test_shipped_retrieval_path_unlocks_retrieval_reference_solutions(shipped):
    tree = shipped.progression.tree
    nodes = [n.id for n in tree.nodes.values() if tree.in_subtree(n, "retrieval")]
    state = TalentState(MAX_LEVEL, "retrieval", frozenset(tree.graph.exercises), tuple(nodes))
    assert "retrieval" in reference_solution_branches(tree, state)
    assert shipped.progression.badges


def test_content_validate_reports_progression_problems_and_counts(content):
    runner = CliRunner()
    write_progression(content, talents="nodes:\n  - id: a\n    title: A\n    summary: s\n")
    failed = runner.invoke(app, ["content", "validate", "--content-dir", str(content)])
    assert failed.exit_code == 1
    assert "talents.yaml: nodes[0].effects" in failed.output

    write_progression(content)
    ok = runner.invoke(app, ["content", "validate", "--content-dir", str(content)])
    assert ok.exit_code == 0 and "0 talents, 0 badges" in ok.output


def test_shipped_flavour_has_a_boss_for_every_capstone(shipped):
    flavour = load_flavour(
        REAL_CONTENT, "rpg", shipped.graph, shipped.progression.tree.path_ids, require_bosses=True
    )
    capstones = {e.id for e in shipped.graph.exercises.values() if e.tier.value == "capstone"}
    assert len(capstones) == 9
    assert set(flavour.bosses) == capstones
