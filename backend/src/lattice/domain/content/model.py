"""Content value objects.

These describe *what* a learner is asked to do and *how* it is checked. They carry no
presentation vocabulary: a theme decides whether a `Branch` is a zone or a track.
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import PurePosixPath
from typing import Annotated, Protocol, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

Slug = Annotated[str, StringConstraints(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=64)]
ExerciseId = Annotated[
    str, StringConstraints(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*\.[a-z0-9]+(?:-[a-z0-9]+)*$")
]
HintText = Annotated[str, StringConstraints(min_length=1, strip_whitespace=True)]


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Tier(StrEnum):
    """Difficulty tier. Capstones close a branch."""

    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    CAPSTONE = "capstone"


class BranchKind(StrEnum):
    """What a branch is for. A project ties the branches it requires into one codebase."""

    STANDARD = "standard"
    PROJECT = "project"


class CheckKind(StrEnum):
    """Deterministic checks test code; behavioural checks test how an AI system behaves."""

    DETERMINISTIC = "deterministic"
    BEHAVIOURAL = "behavioural"


class Check(_Frozen):
    """A named, learner-visible check backed by one pytest test in the exercise's `tests/`."""

    id: Slug
    title: Annotated[str, StringConstraints(min_length=1, max_length=120)]
    test: Annotated[str, StringConstraints(pattern=r"^[\w./-]+\.py::[\w\[\]-]+$")]
    kind: CheckKind = CheckKind.DETERMINISTIC

    @property
    def test_file(self) -> str:
        """The test file relative to the exercise's `tests/` directory."""
        return self.test.split("::", 1)[0]


class Isolation(StrEnum):
    """Where learner code runs during grading (ADR 0009).

    `inprocess` imports it into the interpreter that runs the hidden tests. `process` runs it in
    a child interpreter behind a bridge, so the tests' frames, fakes and modules are out of its
    reach.
    """

    INPROCESS = "inprocess"
    PROCESS = "process"


class Limits(_Frozen):
    """Per-exercise sandbox limits."""

    timeout_s: Annotated[int, Field(ge=1, le=120)] = 20
    memory_mb: Annotated[int, Field(ge=64, le=2048)] = 256


class WrongCase(_Frozen):
    """A known-incorrect solution and the check it must fail. Used to verify content in CI."""

    name: Slug
    fails: Slug
    message_contains: str = ""
    files: dict[str, str]


class Exercise(_Frozen):
    """A single gradable challenge, loaded from `exercise.yaml` and its sibling files."""

    id: ExerciseId
    version: Annotated[int, Field(ge=1)]
    title: Annotated[str, StringConstraints(min_length=1, max_length=120)]
    branch: Slug
    tier: Tier
    xp: Annotated[int, Field(gt=0, le=1000)]
    prerequisites: tuple[ExerciseId, ...] = ()
    # An earlier exercise whose passing files this one opens with, so a project grows one codebase.
    carry_from: ExerciseId | None = None
    skills: tuple[Slug, ...] = ()
    runtime: Slug = "python"
    editable: Annotated[tuple[str, ...], Field(min_length=1)]
    hints: tuple[HintText, ...] = ()  # progressive: revealed one at a time, in order
    checks: Annotated[tuple[Check, ...], Field(min_length=1)]
    limits: Limits = Limits()
    isolation: Isolation = Isolation.INPROCESS
    brief: str
    starter_files: dict[str, str]
    content_hash: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]

    @model_validator(mode="after")
    def _check_consistency(self) -> Self:
        slug_branch = self.id.split(".", 1)[0]
        if slug_branch != self.branch:
            raise ValueError(f"id prefix '{slug_branch}' must match branch '{self.branch}'")
        check_ids = [c.id for c in self.checks]
        if len(check_ids) != len(set(check_ids)):
            raise ValueError("check ids must be unique")
        if self.id in self.prerequisites:
            raise ValueError("an exercise cannot be its own prerequisite")
        if self.isolation is Isolation.PROCESS and self.runtime != "python":
            raise ValueError("isolation 'process' is available for the python runtime only")
        if self.carry_from == self.id:
            raise ValueError("an exercise cannot carry files from itself")
        for path in self.editable:
            if not is_safe_relative_path(path):
                raise ValueError(f"editable path '{path}' must be a safe relative path")
            if path not in self.starter_files:
                raise ValueError(f"editable path '{path}' has no starter file")
        return self


class Branch(_Frozen):
    """A themed-elsewhere group of exercises. `requires` lists branches that must be completed
    before any exercise in this branch unlocks. A `project` branch builds on the branches it
    requires, so it must require at least one."""

    id: Slug
    title: Annotated[str, StringConstraints(min_length=1, max_length=80)]
    summary: str
    order: int
    requires: tuple[Slug, ...] = ()
    kind: BranchKind = BranchKind.STANDARD


def is_safe_relative_path(path: str) -> bool:
    """True for a relative POSIX path with no `..`, absolute root or backslashes."""
    if not path or "\\" in path or "\x00" in path:
        return False
    pure = PurePosixPath(path)
    return not pure.is_absolute() and ".." not in pure.parts


class GradingAssets(Protocol):
    """Access to an exercise's private files, which never leave the grading side."""

    @property
    def exercise(self) -> Exercise: ...

    def tests(self) -> dict[str, str]: ...

    def solution(self) -> dict[str, str]: ...

    def wrong_cases(self) -> tuple[WrongCase, ...]: ...
