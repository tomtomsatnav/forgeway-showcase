"""Content releases: the patch notes behind "What's new" and the learner's unread marker."""

from __future__ import annotations

from fastapi import APIRouter

from lattice.api import schemas
from lattice.api.deps import CurrentLearner, Db, MutatingLearner, State
from lattice.api.schemas import PROBLEM_RESPONSES
from lattice.application import releases
from lattice.infrastructure.content_loader import ContentCatalogue

router = APIRouter(prefix="/api/releases", tags=["releases"], responses=PROBLEM_RESPONSES)


def _exercises(catalogue: ContentCatalogue, ids: tuple[str, ...]) -> list[schemas.ReleaseExercise]:
    # Ids are checked against the content when it loads, so each one is known.
    exercises = catalogue.graph.exercises
    return [
        schemas.ReleaseExercise(id=i, title=exercises[i].title, branch=exercises[i].branch)
        for i in ids
    ]


def _list(view: releases.ReleasesView, catalogue: ContentCatalogue) -> schemas.ReleaseList:
    return schemas.ReleaseList(
        releases=[
            schemas.Release(
                version=n.version,
                date=n.date,
                title=n.title,
                summary=n.summary,
                body=n.body,
                added=_exercises(catalogue, n.added),
                updated=_exercises(catalogue, n.updated),
                fixed=_exercises(catalogue, n.fixed),
            )
            for n in view.releases
        ],
        last_seen=view.last_seen,
        unread=view.unread,
    )


@router.get("")
def list_releases(learner: CurrentLearner, db: Db, state: State) -> schemas.ReleaseList:
    """Every content release, newest first, and whether one is newer than the last seen."""
    return _list(releases.releases_view(db, state.catalogue, learner.user.id), state.catalogue)


@router.post("/seen")
def mark_seen(learner: MutatingLearner, db: Db, state: State) -> schemas.ReleaseList:
    """Mark the newest release as seen, which clears the unread marker. Idempotent."""
    return _list(releases.mark_seen(db, state.catalogue, learner.user.id), state.catalogue)
