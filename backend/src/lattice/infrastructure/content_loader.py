"""Load branches and exercises from the `content/` directory.

Layout::

    content/branches/<branch>/branch.yaml
    content/branches/<branch>/exercises/<slug>/exercise.yaml
                                              /brief.md
                                              /notes.md  (optional; shown with the solution)
                                              /starter/...
                                              /tests/...
                                              /solution/...
                                              /wrong/<case>/expect.yaml + files

Only `exercise.yaml`, `brief.md` and `starter/` become part of the public `Exercise`. Tests,
solutions and wrong cases stay on disk and are read only by the grader and the content checker.

Progression lives beside the branches::

    content/progression/classes.yaml   specialisation paths
    content/progression/talents.yaml   the talent tree
    content/progression/badges.yaml    badges and their criteria

It is optional (a content tree without it has only the generalist path) and is validated
against the branches and exercises it refers to.

Release notes are optional too::

    content/releases/<version>.md      YAML front matter, then the Markdown body

Each file's name must be its version, and every exercise it names must exist.

Showcase copies. A public showcase of this repository omits the private assets (tests, solution
and wrong cases) of every exercise outside the root branch. It says so with a marker file,
``content/SHOWCASE.md``: with it present, an exercise that has none of `tests/`, `solution/` and
`wrong/` loads with its brief and starter only, and grading it fails with a clear message. An
exercise that has any of them is still checked in full, and without the marker nothing changes.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ValidationError

from lattice.domain.content import Branch, ContentError, Exercise, PrerequisiteGraph, WrongCase
from lattice.domain.content.releases import ReleaseNote, newest_first, release_problems
from lattice.domain.progression import (
    Badge,
    Specialisation,
    TalentNode,
    TalentTree,
    badge_problems,
)
from lattice.infrastructure.yaml_loading import load_yaml

_IGNORED_NAMES = {"__pycache__", ".pytest_cache", ".DS_Store"}
SHOWCASE_MARKER = "SHOWCASE.md"
_PRIVATE_ASSETS = ("tests", "solution", "wrong")


@dataclass(frozen=True)
class ExerciseSource:
    """An exercise together with the on-disk directory holding its private grading assets."""

    exercise: Exercise
    root: Path

    def tests(self) -> dict[str, str]:
        """Grading test files, relative to `tests/`."""
        return read_tree(self.root / "tests")

    def solution(self) -> dict[str, str]:
        """Reference solution files, relative to the learner's workspace."""
        return read_tree(self.root / "solution")

    def notes(self) -> str:
        """Optional commentary on the reference solution, shown with it. Empty if none."""
        path = self.root / "notes.md"
        return path.read_text(encoding="utf-8") if path.is_file() else ""

    def wrong_cases(self) -> tuple[WrongCase, ...]:
        """Known-incorrect solutions with the check each must fail."""
        wrong_dir = self.root / "wrong"
        if not wrong_dir.is_dir():
            return ()
        cases = []
        for case_dir in sorted(p for p in wrong_dir.iterdir() if p.is_dir()):
            expect = _read_yaml(case_dir / "expect.yaml")
            files = {k: v for k, v in read_tree(case_dir).items() if k != "expect.yaml"}
            cases.append(WrongCase(name=case_dir.name, files=files, **expect))
        return tuple(cases)


@dataclass(frozen=True)
class ProgressionCatalogue:
    """Paths, the talent tree and badges, already validated against the exercise graph."""

    tree: TalentTree
    badges: tuple[Badge, ...] = ()


@dataclass(frozen=True)
class ContentCatalogue:
    """Everything loaded from a content directory, already validated."""

    graph: PrerequisiteGraph
    sources: dict[str, ExerciseSource]
    progression: ProgressionCatalogue
    releases: tuple[ReleaseNote, ...] = ()  # newest first


def load_catalogue(content_dir: Path) -> ContentCatalogue:
    """Load and validate all content, collecting every problem before failing."""
    problems: list[str] = []
    branches: list[Branch] = []
    sources: dict[str, ExerciseSource] = {}

    showcase = (content_dir / SHOWCASE_MARKER).is_file()
    branches_dir = content_dir / "branches"
    if not branches_dir.is_dir():
        raise ContentError([f"{branches_dir}: directory not found"])

    for branch_dir in sorted(p for p in branches_dir.iterdir() if p.is_dir()):
        branch_file = branch_dir / "branch.yaml"
        try:
            branches.append(Branch(id=branch_dir.name, **_read_yaml(branch_file)))
        except (ValidationError, ContentError, TypeError) as err:
            problems.extend(_describe(branch_file, err))
            continue
        for ex_dir in sorted(p for p in (branch_dir / "exercises").glob("*") if p.is_dir()):
            try:
                exercise = load_exercise(ex_dir, branch=branch_dir.name)
            except (ValidationError, ContentError, TypeError) as err:
                problems.extend(_describe(ex_dir / "exercise.yaml", err))
                continue
            if not (showcase and is_redacted(ex_dir)):
                problems.extend(_check_assets(exercise, ex_dir))
            sources[exercise.id] = ExerciseSource(exercise, ex_dir)

    if problems:
        raise ContentError(problems)
    graph = PrerequisiteGraph(branches, (s.exercise for s in sources.values()))
    return ContentCatalogue(
        graph=graph,
        sources=sources,
        progression=load_progression(content_dir, graph),
        releases=load_releases(content_dir, graph),
    )


def load_releases(content_dir: Path, graph: PrerequisiteGraph) -> tuple[ReleaseNote, ...]:
    """Load `content/releases/*.md`, newest first, collecting every problem before failing."""
    root = content_dir / "releases"
    if not root.is_dir():
        return ()
    problems: list[str] = []
    notes: list[ReleaseNote] = []
    for path in sorted(root.glob("*.md")):
        try:
            meta, body = _front_matter(path)
            note = ReleaseNote.model_validate({**meta, "body": body})
        except ContentError as err:
            problems.extend(err.problems)
            continue
        except ValidationError as err:
            problems.extend(_describe(path, err))
            continue
        if path.stem != note.version:
            problems.append(f"{path}: the file name must be the version, '{note.version}.md'")
        notes.append(note)
    problems.extend(release_problems(notes, graph.exercises))
    if problems:
        raise ContentError(problems)
    return newest_first(notes)


def _front_matter(path: Path) -> tuple[dict[str, Any], str]:
    """Split a Markdown file into its YAML front matter and its body."""
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise ContentError([f"{path}: must start with YAML front matter between '---' lines"])
    head, sep, body = text[4:].partition("\n---\n")
    if not sep:
        raise ContentError([f"{path}: the front matter has no closing '---' line"])
    try:
        meta = load_yaml(head)
    except (yaml.YAMLError, ValueError) as err:  # ValueError: a date such as 2026-13-01
        raise ContentError([f"{path}: invalid YAML front matter: {err}"]) from err
    if not isinstance(meta, dict):
        raise ContentError([f"{path}: the front matter must be a mapping"])
    return meta, body.strip() + "\n"


def load_progression(content_dir: Path, graph: PrerequisiteGraph) -> ProgressionCatalogue:
    """Load `content/progression/`, collecting every problem before failing."""
    root = content_dir / "progression"
    if not root.is_dir():
        return ProgressionCatalogue(TalentTree((), (), graph))
    problems: list[str] = []
    paths = _load_items(root / "classes.yaml", "paths", Specialisation, problems)
    nodes = _load_items(root / "talents.yaml", "nodes", TalentNode, problems)
    badges = _load_items(root / "badges.yaml", "badges", Badge, problems)
    parsed = not problems
    problems.extend(badge_problems(badges, branches=graph.branches))
    tree = None
    if parsed:  # cross-checks make no sense against entries that failed to parse
        try:
            tree = TalentTree(paths, nodes, graph)
        except ContentError as err:
            problems.extend(err.problems)
    if problems or tree is None:
        raise ContentError(problems)
    return ProgressionCatalogue(tree, tuple(badges))


def load_exercise(ex_dir: Path, *, branch: str) -> Exercise:
    """Load one exercise directory into a validated `Exercise`."""
    meta = _read_yaml(ex_dir / "exercise.yaml")
    brief_path = ex_dir / "brief.md"
    if not brief_path.is_file():
        raise ContentError([f"{brief_path}: missing"])
    return Exercise(
        id=f"{branch}.{ex_dir.name}",
        branch=branch,
        brief=brief_path.read_text(encoding="utf-8"),
        starter_files=read_tree(ex_dir / "starter"),
        content_hash=hash_tree(ex_dir),
        **meta,
    )


def is_redacted(ex_dir: Path) -> bool:
    """True if a showcase copy has omitted all of this exercise's private assets."""
    return not any((ex_dir / name).exists() for name in _PRIVATE_ASSETS)


def _check_assets(exercise: Exercise, ex_dir: Path) -> list[str]:
    """Problems with an exercise's private assets: missing tests, solution or wrong cases."""
    where = ex_dir / "exercise.yaml"
    problems: list[str] = []
    tests = read_tree(ex_dir / "tests")
    for check in exercise.checks:
        test_file = check.test.split("::", 1)[0]
        if test_file not in tests:
            problems.append(f"{where}: check '{check.id}' points at missing tests/{test_file}")
        elif f"def {check.test.split('::', 1)[1].split('[', 1)[0]}(" not in tests[test_file]:
            problems.append(f"{where}: check '{check.id}' test function not found in {test_file}")
    solution = read_tree(ex_dir / "solution")
    problems.extend(
        f"{where}: solution/ is missing editable file '{path}'"
        for path in exercise.editable
        if path not in solution
    )
    try:
        cases = ExerciseSource(exercise, ex_dir).wrong_cases()
    except (ValidationError, ContentError, TypeError) as err:
        return [*problems, *_describe(ex_dir / "wrong", err)]
    if not cases:
        problems.append(f"{where}: needs at least one wrong/<case>/ to prove failures are useful")
    check_ids = {c.id for c in exercise.checks}
    for case in cases:
        if case.fails not in check_ids:
            problems.append(f"{where}: wrong case '{case.name}' names unknown check '{case.fails}'")
        problems.extend(
            f"{where}: wrong case '{case.name}' has non-editable file '{path}'"
            for path in case.files
            if path not in exercise.editable
        )
    return problems


def _load_items[T: BaseModel](path: Path, key: str, model: type[T], problems: list[str]) -> list[T]:
    """Validate each entry under `key` in a YAML file, adding every problem to `problems`."""
    try:
        items = _read_yaml(path).get(key, [])
        if not isinstance(items, list):
            raise ContentError([f"{path}: '{key}' must be a list"])
    except ContentError as err:
        problems.extend(err.problems)
        return []
    loaded: list[T] = []
    for index, item in enumerate(items):
        try:
            loaded.append(model.model_validate(item))
        except ValidationError as err:
            problems.extend(_describe(path, err, prefix=f"{key}[{index}]"))
    return loaded


def read_tree(root: Path) -> dict[str, str]:
    """Read every text file under `root`, keyed by POSIX path relative to `root`."""
    if not root.is_dir():
        return {}
    return {
        path.relative_to(root).as_posix(): path.read_text(encoding="utf-8")
        for path in sorted(root.rglob("*"))
        if path.is_file() and not _IGNORED_NAMES.intersection(path.parts)
    }


def hash_tree(root: Path) -> str:
    """Stable SHA-256 over every file's relative path and bytes."""
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if path.is_file() and not _IGNORED_NAMES.intersection(path.parts):
            digest.update(path.relative_to(root).as_posix().encode())
            digest.update(b"\0")
            digest.update(path.read_bytes())
            digest.update(b"\0")
    return digest.hexdigest()


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ContentError([f"{path}: missing"])
    try:
        data = load_yaml(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as err:
        raise ContentError([f"{path}: invalid YAML: {err}"]) from err
    if not isinstance(data, dict):
        raise ContentError([f"{path}: expected a mapping at the top level"])
    return data


def _describe(path: Path, err: Exception, prefix: str = "") -> list[str]:
    if isinstance(err, ValidationError):
        return [
            f"{path}: {'.'.join([*([prefix] if prefix else []), *map(str, e['loc'])]) or '<root>'}"
            f": {e['msg']}"
            for e in err.errors()
        ]
    if isinstance(err, ContentError):
        return list(err.problems)
    return [f"{path}: {err}"]
