"""The learner map, exercises, hints, drafts and attempts."""

from __future__ import annotations

import uuid
from datetime import timedelta

from fastapi import APIRouter, Request, Response, status

from lattice.api import schemas
from lattice.api.deps import (
    SESSION_COOKIE,
    AppState,
    CurrentLearner,
    Db,
    Learner,
    MutatingLearner,
    State,
    VerifiedLearner,
)
from lattice.api.schemas import PROBLEM_RESPONSES
from lattice.application import accounts, learning, live_runs, local_live, plans
from lattice.application.errors import NotFoundError
from lattice.domain.entitlements import is_paid
from lattice.infrastructure.theme_flavour import ThemeFlavour

router = APIRouter(prefix="/api", tags=["learning"], responses=PROBLEM_RESPONSES)
DOWNLOADS_PER_HOUR = 60  # per account: a whole track, several times over


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
    return _exercise_detail(_view(db, state, learner, exercise_id), state)


def _view(db: Db, state: State, learner: Learner, exercise_id: str) -> learning.ExerciseView:
    return learning.exercise_view(
        db,
        state.catalogue,
        learner.user.id,
        exercise_id,
        free_per_branch=state.settings.free_exercises_per_branch,
    )


def _exercise_detail(view: learning.ExerciseView, state: State) -> schemas.ExerciseDetail:
    ex = view.exercise
    if not view.entitled:
        # A Pro exercise on the free plan: no brief, files, checks or hints, only what the map
        # shows. The learner's own attempts stay listed.
        return schemas.ExerciseDetail(
            id=ex.id, branch=ex.branch, title=ex.title, tier=ex.tier.value, xp=ex.xp,
            status=view.status, pro=view.pro, entitled=False,
            prerequisites=list(ex.prerequisites), brief="", editable=[], files={},
            files_source="starter", carried_from=None, checks=[], hints_total=0,
            hints_revealed=[],
            recent_attempts=[
                schemas.AttemptSummary(id=a.id, status=a.status, created_at=a.created_at)
                for a in view.recent_attempts
            ],
        )  # fmt: skip
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
        has_live_example=live_runs.has_live_example(state.catalogue, ex.id),
        python_notes=view.python_notes,
    )


@router.get(
    "/exercises/{exercise_id}/download",
    response_class=Response,
    responses={200: {"content": {"application/zip": {}}, "description": "The exercise as a zip"}},
)
def download_exercise(exercise_id: str, learner: CurrentLearner, db: Db, state: State) -> Response:
    """The exercise to run locally against a real model: the brief, the learner's current files,
    the optional `live.py` and a README on live mode. Never tests, solutions or wrong cases, and
    never a key: live mode reads the learner's own key on their own machine.

    A Pro exercise needs a Pro or Team plan (403 `plan-required`)."""
    settings = state.settings
    state.limiter.check(
        f"download:user:{learner.user.id}",
        limit=DOWNLOADS_PER_HOUR,
        window=timedelta(hours=1),
        message="You have downloaded a lot of exercises this hour. Try again later.",
    )
    body = local_live.exercise_download(
        db,
        state.catalogue,
        learner.user.id,
        exercise_id,
        free_per_branch=settings.free_exercises_per_branch,
        kit_url=local_live.kit_wheel_url(settings.kit_dir, settings.public_base_url),
        guide_url=settings.public_base_url.rstrip("/") + local_live.GUIDE_PAGE,
        guide_path=settings.live_mode_guide,
    )
    return Response(
        body,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{exercise_id}.zip"',
            "Cache-Control": "no-store",  # it holds the learner's draft
        },
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


def require_entitled(state: AppState, learner: Learner, exercise_id: str) -> None:
    """404 for an unknown exercise, then 403 `plan-required` unless the plan includes it."""
    if exercise_id not in state.catalogue.sources:
        raise NotFoundError(f"No exercise called '{exercise_id}'.")
    plans.require_attempt_entitlement(
        learner.user, state.catalogue.graph, exercise_id, state.settings.free_exercises_per_branch
    )


@router.put("/exercises/{exercise_id}/draft", status_code=status.HTTP_204_NO_CONTENT)
def save_draft(
    exercise_id: str, body: schemas.FilesBody, learner: MutatingLearner, db: Db, state: State
) -> None:
    """A Pro exercise's draft needs a Pro or Team plan (403 `plan-required`)."""
    require_entitled(state, learner, exercise_id)
    learning.save_draft(db, state.catalogue, learner.user.id, exercise_id, body.files)


@router.delete("/exercises/{exercise_id}/draft")
def reset_draft(
    exercise_id: str, learner: MutatingLearner, db: Db, state: State
) -> schemas.ExerciseDetail:
    """Discard the draft and any carried files: the exercise opens on its starter files from now
    on. Answers with the exercise as it now opens. A Pro exercise needs a Pro or Team plan (403
    `plan-required`)."""
    require_entitled(state, learner, exercise_id)
    learning.reset_to_starter(db, state.catalogue, learner.user.id, exercise_id)
    return _exercise_detail(_view(db, state, learner, exercise_id), state)


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
def rpg_flavour(request: Request, db: Db, state: State) -> ThemeFlavour:
    """Zone names, quest titles and lore for the RPG presentation. Public, with no sign-in.

    A boss guards a capstone, which is Pro, so its lore and defeat text go only to a signed-in
    learner on a paid plan; everyone else gets its name and epithet, as they get titles."""
    token = request.cookies.get(SESSION_COOKIE)
    resolved = accounts.resolve_session(db, token) if token else None
    flavour = state.rpg_flavour
    if resolved is not None and is_paid(plans.plan_of(resolved[0])):
        return flavour
    bosses = {i: b.model_copy(update={"lore": "", "defeat": ""}) for i, b in flavour.bosses.items()}
    return flavour.model_copy(update={"bosses": bosses})


@router.get("/catalogue")
def catalogue(state: State, response: Response) -> schemas.Catalogue:
    """Every branch and exercise as a brand-new learner on the free plan sees them: nothing
    passed, Pro marked by the free plan. Public and cacheable; it reads nothing about anyone, so
    the landing page can show the syllabus before anyone signs in."""
    response.headers["Cache-Control"] = "public, max-age=300"
    views = learning.catalogue_view(
        state.catalogue, free_per_branch=state.settings.free_exercises_per_branch
    )
    return schemas.Catalogue(
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
            for b in views
        ]
    )  # fmt: skip
