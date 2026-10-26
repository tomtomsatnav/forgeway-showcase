"""Scaffold a new exercise directory that validates at once and grades as soon as it is written.

The scaffold is a small, complete exercise: one editable module, one check whose test
canonicalises what learner code returns and works out the expected value only after the learner
call, a reference solution that passes it and a wrong case that fails it. The author replaces
each part; `forgeway content validate` and `forgeway content test --only <id>` pass throughout.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from lattice.domain.content import BranchKind, Tier
from lattice.infrastructure.content_loader import ContentCatalogue

DEFAULT_XP = {Tier.BEGINNER: 50, Tier.INTERMEDIATE: 100, Tier.ADVANCED: 150, Tier.CAPSTONE: 300}
_SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class ScaffoldError(Exception):
    """The exercise cannot be scaffolded as asked. Nothing has been written."""


@dataclass(frozen=True)
class Scaffold:
    """What `scaffold_exercise` wrote, for the caller to report."""

    exercise_id: str
    root: Path
    files: tuple[str, ...]
    # Capstone whose prerequisites gained the new exercise, so the branch still validates.
    linked_capstone: str | None = None
    notes: tuple[str, ...] = field(default=())


def scaffold_exercise(
    content_dir: Path,
    catalogue: ContentCatalogue,
    branch: str,
    slug: str,
    *,
    tier: Tier = Tier.BEGINNER,
    title: str | None = None,
    carry_from: str | None = None,
) -> Scaffold:
    """Write `content/branches/<branch>/exercises/<slug>/`. Refuses to overwrite anything."""
    graph = catalogue.graph
    if branch not in graph.branches:
        raise ScaffoldError(f"unknown branch '{branch}'")
    if not _SLUG.match(slug) or len(slug) > 64:
        raise ScaffoldError(f"'{slug}' is not a slug: lower-case words joined by hyphens")
    exercise_id = f"{branch}.{slug}"
    root = content_dir / "branches" / branch / "exercises" / slug
    if root.exists():
        raise ScaffoldError(f"{root} already exists; refusing to overwrite it")

    siblings = graph.branch_exercises(branch)
    capstone = next((e for e in siblings if e.tier is Tier.CAPSTONE), None)
    if tier is Tier.CAPSTONE:
        if capstone is not None:
            raise ScaffoldError(f"branch '{branch}' already has a capstone: '{capstone.id}'")
        if not graph.branches[branch].requires:
            raise ScaffoldError(f"branch '{branch}' requires nothing, so it has no capstone")

    prerequisites: list[str] = []
    editable: list[str] = []
    carried_starter: dict[str, str] = {}
    carried_solution: dict[str, str] = {}
    if carry_from is not None:
        carry_from = carry_from if "." in carry_from else f"{branch}.{carry_from}"
        if graph.branches[branch].kind is not BranchKind.PROJECT:
            raise ScaffoldError(f"--carry-from is for project branches; '{branch}' is not one")
        source = catalogue.sources.get(carry_from)
        if source is None or source.exercise.branch != branch:
            raise ScaffoldError(f"'{carry_from}' is not an exercise in '{branch}'")
        if source.exercise.tier is Tier.CAPSTONE:
            raise ScaffoldError(f"'{carry_from}' is the capstone; nothing may build on it")
        # The milestone's starter is the previous milestone's reference solution, so it stands on
        # its own for anyone who resets.
        solution = source.solution()
        editable = list(source.exercise.editable)
        carried_starter = {p: solution[p] for p in editable}
        carried_solution = dict(carried_starter)
        prerequisites = [carry_from]
    if tier is Tier.CAPSTONE:
        prerequisites = _branch_leaves(catalogue, branch)

    module = slug.replace("-", "_")
    if f"{module}.py" in editable:
        raise ScaffoldError(f"'{carry_from}' already has {module}.py; pick another slug")
    editable.append(f"{module}.py")
    title = title or slug.replace("-", " ").capitalize()

    files = {
        "exercise.yaml": _exercise_yaml(title, tier, module, editable, prerequisites, carry_from),
        "brief.md": _BRIEF.format(title=title, module=module),
        **{f"starter/{p}": text for p, text in carried_starter.items()},
        f"starter/{module}.py": _STARTER.format(title=title),
        f"tests/test_{module}.py": _TEST.format(module=module),
        **{f"solution/{p}": text for p, text in carried_solution.items()},
        f"solution/{module}.py": _SOLUTION.format(title=title),
        f"wrong/loses-the-order/{module}.py": _WRONG.format(title=title),
        "wrong/loses-the-order/expect.yaml": "fails: example\nmessage_contains: original order\n",
    }

    linked = None
    notes: list[str] = []
    if capstone is not None and tier is not Tier.CAPSTONE:
        capstone_yaml = catalogue.sources[capstone.id].root / "exercise.yaml"
        if _add_prerequisite(capstone_yaml, exercise_id):
            linked = capstone.id
        else:
            notes.append(
                f"add '{exercise_id}' to the prerequisites of capstone '{capstone.id}' "
                f"({capstone_yaml}): a capstone must depend on every exercise in its branch"
            )

    for rel, text in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return Scaffold(exercise_id, root, tuple(files), linked, tuple(notes))


def _branch_leaves(catalogue: ContentCatalogue, branch: str) -> list[str]:
    """Exercises in the branch that nothing else in it depends on: enough for a capstone's
    prerequisites to reach the whole branch."""
    own = catalogue.graph.branch_exercises(branch)
    needed = {pre for e in own for pre in e.prerequisites}
    return [e.id for e in own if e.id not in needed]


def _add_prerequisite(path: Path, exercise_id: str) -> bool:
    """Append `exercise_id` to the prerequisites in `path`, keeping the rest of the file as it
    is. Handles a one-line flow list and a block list; returns False (writing nothing) for any
    other shape."""
    text = path.read_text(encoding="utf-8")
    before = yaml.safe_load(text).get("prerequisites") or []
    lines = text.splitlines(keepends=True)
    index = next((i for i, ln in enumerate(lines) if ln.startswith("prerequisites:")), None)
    if index is None:
        return False
    value = lines[index].split(":", 1)[1].strip()
    if value.startswith("[") and value.endswith("]"):
        items = [*before, exercise_id]
        lines[index] = f"prerequisites: [{', '.join(items)}]\n"
    elif value == "":
        last = index
        while last + 1 < len(lines) and re.match(r"^\s*- ", lines[last + 1]):
            last += 1
        if last == index:
            return False
        indent = lines[last][: len(lines[last]) - len(lines[last].lstrip())]
        lines.insert(last + 1, f"{indent}- {exercise_id}\n")
    else:
        return False
    updated = "".join(lines)
    try:
        after = yaml.safe_load(updated).get("prerequisites")
    except yaml.YAMLError:
        return False
    if after != [*before, exercise_id]:
        return False
    path.write_text(updated, encoding="utf-8")
    return True


def _exercise_yaml(
    title: str,
    tier: Tier,
    module: str,
    editable: list[str],
    prerequisites: list[str],
    carry_from: str | None,
) -> str:
    lines = [
        "version: 1  # bump when a change could alter whether a solution passes",
        f"title: {_yaml_scalar(title)}",
        f"tier: {tier.value}",
        f"xp: {DEFAULT_XP[tier]}",
        f"prerequisites: [{', '.join(prerequisites)}]",
    ]
    if carry_from is not None:
        lines.append(f"carry_from: {carry_from}")
    lines += [
        "isolation: process  # learner code runs in a child process (ADR 0009)",
        "skills: []",
        f"editable: [{', '.join(editable)}]",
    ]
    if tier is Tier.CAPSTONE:
        lines.append("limits: { timeout_s: 60, memory_mb: 512 }")
    lines += [
        "hints:  # progressive: each one gives away a little more",
        '  - "Replace this with a hint that points at the idea, not the answer."',
        "checks:",
        "  - id: example",
        "    title: Replace this with what the check proves",
        f"    test: test_{module}.py::test_example",
        "",
    ]
    return "\n".join(lines)


def _yaml_scalar(text: str) -> str:
    dumped: str = yaml.safe_dump(text, default_flow_style=True, width=1000)
    return dumped.removesuffix("\n...\n").strip()


_BRIEF = """\
# {title}

Replace this paragraph with why the idea matters: the problem a working engineer meets and what
goes wrong without it.

```python
from {module} import shout

shout(["tea", "toast"])  # ["TEA", "TOAST"]
```

## Your task

Implement `shout(words)` in `{module}.py`. It returns every word in `words` upper-cased, in the
original order.

State every rule a check enforces (formats, defaults, boundaries) here, and nothing it does not.
"""

_STARTER = '''\
"""{title}."""


def shout(words: list[str]) -> list[str]:
    """Return every word upper-cased, in the original order."""
    raise NotImplementedError
'''

_SOLUTION = '''\
"""{title}."""


def shout(words: list[str]) -> list[str]:
    """Return every word upper-cased, in the original order."""
    return [word.upper() for word in words]
'''

_WRONG = '''\
"""{title}."""


def shout(words: list[str]) -> list[str]:
    """Return every word upper-cased, in the original order."""
    return sorted(word.upper() for word in words)
'''

_TEST = '''\
"""Hidden checks. Learners see each check's title and, when it fails, the assertion message."""

import json
import random

from {module} import shout


def plain(value):
    """Learner results as plain built-ins, so a value cannot lie about equality."""
    return json.loads(json.dumps(value))


def expected(words):
    """What shout() should return. Call it only after learner code has returned, so the answer
    is never in a frame learner code can read."""
    return [word.upper() for word in words]


def test_example():
    rng = random.Random(0)  # noqa: S311 - seeded, so grading is deterministic
    words = ["".join(rng.choice("abcdefgh") for _ in range(5)) for _ in range(8)]
    result = plain(shout(list(words)))
    want = expected(words)
    assert result == want, (
        f"shout({{words!r}}) should return {{want!r}}, but returned {{result!r}}. "
        "Keep the words in their original order."
    )
'''
