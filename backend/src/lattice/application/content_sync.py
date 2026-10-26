"""Mirror the public part of on-disk content into the database."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from lattice.domain.content import Exercise, PrerequisiteGraph
from lattice.infrastructure.db.engine import rowcount
from lattice.infrastructure.db.models import BranchRow, ExerciseRevision


@dataclass(frozen=True)
class SyncSummary:
    new_revisions: int
    retired: int


def sync_content(session: Session, graph: PrerequisiteGraph) -> SyncSummary:
    """Idempotently record branches and one revision per distinct exercise content hash."""
    for position, branch in enumerate(sorted(graph.branches.values(), key=lambda b: b.order)):
        session.merge(
            BranchRow(
                id=branch.id,
                title=branch.title,
                summary=branch.summary,
                position=position,
                requires=list(branch.requires),
            )
        )

    known = {row.content_hash: row for row in session.scalars(select(ExerciseRevision))}
    new = 0
    for exercise in graph.exercises.values():
        existing = known.get(exercise.content_hash)
        if existing is not None and existing.is_current:
            continue
        session.execute(
            update(ExerciseRevision)
            .where(ExerciseRevision.exercise_id == exercise.id, ExerciseRevision.is_current)
            .values(is_current=False)
        )
        session.flush()
        if existing is not None:
            existing.is_current = True
        else:
            session.add(_revision(exercise))
            new += 1

    retired = rowcount(
        session.execute(
            update(ExerciseRevision)
            .where(
                ExerciseRevision.is_current,
                ExerciseRevision.exercise_id.not_in(list(graph.exercises)),
            )
            .values(is_current=False)
        )
    )
    session.flush()
    return SyncSummary(new_revisions=new, retired=retired)


def current_revision_ids(session: Session) -> dict[str, int]:
    """Exercise id -> id of its current revision."""
    rows = session.execute(
        select(ExerciseRevision.exercise_id, ExerciseRevision.id).where(ExerciseRevision.is_current)
    )
    return {exercise_id: revision_id for exercise_id, revision_id in rows.all()}  # noqa: C416


def _revision(exercise: Exercise) -> ExerciseRevision:
    return ExerciseRevision(
        exercise_id=exercise.id,
        version=exercise.version,
        content_hash=exercise.content_hash,
        definition=exercise.model_dump(mode="json"),
        is_current=True,
    )
