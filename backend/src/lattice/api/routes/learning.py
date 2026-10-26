"""The learner map, exercises, hints, drafts and attempts."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, status

from lattice.api import schemas
from lattice.api.deps import CurrentLearner, Db, Learner, MutatingLearner, State, VerifiedLearner
from lattice.api.schemas import PROBLEM_RESPONSES
from lattice.application import learning
from lattice.infrastructure.theme_flavour import ThemeFlavour

router = APIRouter(prefix="/api", tags=["learning"], responses=PROBLEM_RESPONSES)


@router.get("/map")
def learner_map(learner: CurrentLearner, db: Db, state: State) -> schemas.LearnerMap:
    """Every branch and exercise with the learner's status, plus their level."""
    view = learning.learner_map(
        db,
        state.catalogue,
        learner.user.id,
        free_per_branch=state.settings.free_exercises_per_branch,
    )
    level = view.level
    return schemas.LearnerMap(
        branches=[
            schemas.BranchSummary(
                id=b.id,
                title=b.title,
                summary=b.summary,
                unlocked=b.unlocked,
                requires=list(b.requires),
                kind=b.kind,
                passed_count=b.passed_count,
                pro=b.pro,
                exercises=[
                    schemas.ExerciseSummary(
                        id=e.id, title=e.title, tier=e.tier, xp=e.xp,
                        skills=list(e.skills), prerequisites=list(e.prerequisites),
                        status=e.status, pro=e.pro, entitled=e.entitled,
                    )
                    for e in b.exercises
                ],
            )
            for b in view.branches
        ],
        level=schemas.Level(
            level=level.level,
            total_xp=level.total_xp,
            level_floor=level.level_floor,
            next_level_at=level.next_level_at,
            fraction=level.fraction,
        ),
        streak=schemas.Streak(current=view.streak.current, longest=view.streak.longest),
    )  # fmt: skip


@router.get("/exercises/{exercise_id}")
def get_exercise(
    exercise_id: str, learner: CurrentLearner, db: Db, state: State
) -> schemas.ExerciseDetail:
    """The brief, the learner's current files and their recent attempts."""
    return _exercise_detail(_view(db, state, learner, exercise_id))


def _view(db: Db, state: State, learner: Learner, exercise_id: str) -> learning.ExerciseView:
    return learning.exercise_view(
        db,
        state.catalogue,
        learner.user.id,
        exercise_id,
        free_per_branch=state.settings.free_exercises_per_branch,
    )


def _exercise_detail(view: learning.ExerciseView) -> schemas.ExerciseDetail:
    ex = view.exercise
    return schemas.ExerciseDetail(
        id=ex.id,
        branch=ex.branch,
        title=ex.title,
        tier=ex.tier.value,
        xp=ex.xp,
        status=view.status,
        pro=view.pro,
        entitled=view.entitled,
        prerequisites=list(ex.prerequisites),
        brief=ex.brief,
        editable=list(ex.editable),
        files=view.files,
        files_source=view.files_source,
        carried_from=view.carried_from,
        checks=[schemas.CheckInfo(id=c.id, title=c.title, kind=c.kind.value) for c in ex.checks],
        hints_total=len(ex.hints),
        hints_revealed=list(view.hints_revealed),
        recent_attempts=[
            schemas.AttemptSummary(id=a.id, status=a.status, created_at=a.created_at)
            for a in view.recent_attempts
        ],
    )


@router.post("/exercises/{exercise_id}/hints")
def reveal_hint(exercise_id: str, learner: MutatingLearner, db: Db, state: State) -> schemas.Hints:
    """Reveal the next hint. Revealing any hint forfeits the no-hint bonus.

    A Pro exercise's hints need a Pro or Team plan (403 `plan-required`)."""
    revealed = learning.reveal_next_hint(
        db,
        state.catalogue,
        learner.user.id,
        exercise_id,
        free_per_branch=state.settings.free_exercises_per_branch,
    )
    total = len(state.catalogue.sources[exercise_id].exercise.hints)
    return schemas.Hints(hints_revealed=list(revealed), hints_total=total)


@router.put("/exercises/{exercise_id}/draft", status_code=status.HTTP_204_NO_CONTENT)
def save_draft(
    exercise_id: str, body: schemas.FilesBody, learner: MutatingLearner, db: Db, state: State
) -> None:
    learning.save_draft(db, state.catalogue, learner.user.id, exercise_id, body.files)


@router.delete("/exercises/{exercise_id}/draft")
def reset_draft(
    exercise_id: str, learner: MutatingLearner, db: Db, state: State
) -> schemas.ExerciseDetail:
    """Discard the draft and any carried files: the exercise opens on its starter files from now
    on. Answers with the exercise as it now opens."""
    learning.reset_to_starter(db, state.catalogue, learner.user.id, exercise_id)
    return _exercise_detail(_view(db, state, learner, exercise_id))


@router.post("/exercises/{exercise_id}/attempts", status_code=status.HTTP_202_ACCEPTED)
def submit_attempt(
    exercise_id: str, body: schemas.FilesBody, learner: VerifiedLearner, db: Db, state: State
) -> schemas.AttemptDetail:
    """Queue the learner's files for grading. Poll the returned attempt for the result.

    Needs a verified email (403 `email-unverified`) and, for a Pro exercise, a Pro or Team plan
    (403 `plan-required`). One attempt at a time per learner (409 `attempt-in-flight`), a
    per-minute cap (429 `rate-limited`), a daily cap on attempts (429 `attempt-daily-cap`, with
    `limit`) and on grading time (429 `grading-budget`, with `budget_minutes`), and a full
    grading queue answers 503 `busy` with Retry-After.
    """
    attempt = learning.submit_attempt(
        db,
        state.catalogue,
        state.revision_ids,
        learner.user.id,
        exercise_id,
        body.files,
        per_minute_limit=state.settings.attempts_per_minute,
        per_day_limit=state.settings.attempts_per_day,
        max_queue_depth=state.settings.max_queue_depth,
        grading_seconds_per_day=state.settings.grading_seconds_per_day,
        free_per_branch=state.settings.free_exercises_per_branch,
    )
    learning.save_draft(db, state.catalogue, learner.user.id, exercise_id, body.files)
    return schemas.AttemptDetail.from_row(attempt)


@router.get("/attempts/{attempt_id}")
def get_attempt(attempt_id: uuid.UUID, learner: CurrentLearner, db: Db) -> schemas.AttemptDetail:
    return schemas.AttemptDetail.from_row(learning.get_attempt(db, learner.user.id, attempt_id))


@router.get("/themes/rpg/flavour")
def rpg_flavour(state: State) -> ThemeFlavour:
    """Zone names, quest titles and lore for the RPG presentation. Public and cacheable."""
    return state.rpg_flavour
