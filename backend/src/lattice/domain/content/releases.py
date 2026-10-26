"""Content releases: the patch notes behind "What's new" (the Chronicle in RPG mode).

Each release is a Markdown file, `content/releases/<version>.md`, whose YAML front matter names
the version, the date and the exercises it added, updated or fixed. Versions are calendar
versions, `YYYY.MM.N`, so they sort in release order.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, StringConstraints, model_validator

from lattice.domain.content.model import Exercise, ExerciseId

ReleaseVersion = Annotated[str, StringConstraints(pattern=r"^\d{4}\.(?:[1-9]|1[0-2])\.\d+$")]


def version_key(version: str) -> tuple[int, ...]:
    """A sortable key for a release version: `2026.10.0` -> (2026, 10, 0)."""
    return tuple(int(part) for part in version.split("."))


class ReleaseNote(BaseModel):
    """One content release, as its front matter and Markdown body describe it."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    version: ReleaseVersion
    date: date
    title: Annotated[str, StringConstraints(min_length=1, max_length=120)]
    summary: Annotated[str, StringConstraints(min_length=1, max_length=400)]
    added: tuple[ExerciseId, ...] = ()
    updated: tuple[ExerciseId, ...] = ()
    fixed: tuple[ExerciseId, ...] = ()
    body: str = ""

    @model_validator(mode="after")
    def _ids_listed_once(self) -> Self:
        for name, ids in (("added", self.added), ("updated", self.updated), ("fixed", self.fixed)):
            if len(ids) != len(set(ids)):
                raise ValueError(f"'{name}' lists an exercise more than once")
        return self

    @property
    def exercise_ids(self) -> tuple[str, ...]:
        return (*self.added, *self.updated, *self.fixed)


def release_problems(notes: Iterable[ReleaseNote], exercises: Mapping[str, Exercise]) -> list[str]:
    """Every breach of the release rules: unique versions, and only exercises that exist."""
    problems: list[str] = []
    seen: set[str] = set()
    for note in notes:
        if note.version in seen:
            problems.append(f"release '{note.version}' is defined more than once")
        seen.add(note.version)
        problems.extend(
            f"release '{note.version}' names unknown exercise '{exercise_id}'"
            for exercise_id in note.exercise_ids
            if exercise_id not in exercises
        )
    return problems


def newest_first(notes: Iterable[ReleaseNote]) -> tuple[ReleaseNote, ...]:
    return tuple(sorted(notes, key=lambda n: version_key(n.version), reverse=True))


def has_unread(notes: Iterable[ReleaseNote], last_seen: str | None) -> bool:
    """Whether a release is newer than the one the learner last saw (any release, if none)."""
    keys = [version_key(n.version) for n in notes]
    if not keys:
        return False
    return last_seen is None or max(keys) > version_key(last_seen)
