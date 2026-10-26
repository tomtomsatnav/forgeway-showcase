"""Build throwaway content trees on disk for tests."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

PASSING_TEST = (
    "from solution_mod import add\n\n"
    "def test_adds():\n"
    "    assert add(2, 2) == 4, 'add(2, 2) should be 4'\n"
)


def write_branch(root: Path, branch: str, **meta: Any) -> Path:
    branch_dir = root / "branches" / branch
    (branch_dir / "exercises").mkdir(parents=True, exist_ok=True)
    meta = {"title": branch.title(), "summary": "s", "order": 0, **meta}
    (branch_dir / "branch.yaml").write_text(yaml.safe_dump(meta))
    return branch_dir


def write_exercise(root: Path, branch: str, slug: str, **overrides: Any) -> Path:
    ex_dir = root / "branches" / branch / "exercises" / slug
    meta: dict[str, Any] = {
        "version": 1,
        "title": slug.replace("-", " ").title(),
        "tier": "beginner",
        "xp": 100,
        "editable": ["solution_mod.py"],
        "checks": [{"id": "adds", "title": "Adds numbers", "test": "test_add.py::test_adds"}],
        **overrides,
    }
    files = {
        "exercise.yaml": yaml.safe_dump(meta),
        "brief.md": f"# {slug}\n",
        "starter/solution_mod.py": "def add(a, b):\n    raise NotImplementedError\n",
        "tests/test_add.py": PASSING_TEST,
        "solution/solution_mod.py": "def add(a, b):\n    return a + b\n",
        "wrong/subtracts/solution_mod.py": "def add(a, b):\n    return a - b\n",
        "wrong/subtracts/expect.yaml": "fails: adds\nmessage_contains: should be 4\n",
    }
    for rel, text in files.items():
        path = ex_dir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    return ex_dir
