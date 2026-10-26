"""Path and time zone, the talent tree, badges and reference solutions."""

from __future__ import annotations

import uuid

from fastapi import APIRouter

from lattice.api import schemas
from lattice.api.deps import AppState, CurrentLearner, Db, MutatingLearner, State
from lattice.api.schemas import PROBLEM_RESPONSES
from lattice.application import progression
from lattice.domain.progression import (
    BranchComplete,
    Criterion,
    ReferenceSolutionsEffect,
    TitleEffect,
)

router = APIRouter(prefix="/api", tags=["progression"], responses=PROBLEM_RESPONSES)


def _profile(view: progression.ProfileView, dropped: tuple[str, ...] = ()) -> schemas.PathProfile:
    return schemas.PathProfile(
        path=view.path,
        time_zone=view.time_zone,
        titles=list(view.titles),
        paths=[
            schemas.PathOption(
                id=p.id,
                title=p.title,
                summary=p.summary,
                home_branch=p.home_branch,
                selectable=p.selectable,
                reason=p.reason,
                requires=[schemas.BranchRef(id=i, title=t) for i, t in p.requires],
            )
            for p in view.paths
        ],
        dropped_talents=list(dropped),
    )


def _requirement(criterion: Criterion, state: AppState) -> schemas.BadgeRequirement:
    if isinstance(criterion, BranchComplete):
        branch = state.catalogue.graph.branches.get(criterion.branch)
        title = branch.title if branch else criterion.branch
        return schemas.BadgeRequirement(
            kind=criterion.kind, branch=schemas.BranchRef(id=criterion.branch, title=title)
        )
    return schemas.BadgeRequirement(kind=criterion.kind, n=criterion.n)


def _tree(view: progression.TalentTreeView) -> schemas.TalentTree:
    return schemas.TalentTree(
        path=view.path,
        total_points=view.total_points,
        spent_points=view.spent_points,
        available_points=view.available_points,
        nodes=[
            schemas.TalentNode(
                id=n.node.id,
                title=n.node.title,
                summary=n.node.summary,
                subtree=n.node.subtree,
                parents=list(n.node.parents),
                min_level=n.node.min_level,
                required_exercises=list(n.node.required_exercises),
                effects=[
                    schemas.TalentEffect(kind="title", value=e.title)
                    if isinstance(e, TitleEffect)
                    else schemas.TalentEffect(
                        kind="reference_solutions", value=e.reference_solutions
                    )
                    for e in n.node.effects
                    if isinstance(e, TitleEffect | ReferenceSolutionsEffect)
                ],
                state=n.status.state,
                reasons=[
                    schemas.Blocker(code=b.code.value, detail=b.detail) for b in n.status.blockers
                ],
            )
            for n in view.nodes
        ],
    )


@router.get("/profile")
def get_profile(learner: CurrentLearner, db: Db, state: State) -> schemas.PathProfile:
    """The learner's path, time zone and titles, and the paths they could choose."""
    return _profile(_profile_view(db, state, learner.user.id))


def _profile_view(db: Db, state: State, user_id: uuid.UUID) -> progression.ProfileView:
    return progression.profile_view(
        db, state.catalogue, user_id, free_per_branch=state.settings.free_exercises_per_branch
    )


@router.put("/profile")
def update_profile(
    body: schemas.PathProfileUpdate, learner: MutatingLearner, db: Db, state: State
) -> schemas.PathProfile:
    """Change path and/or time zone. Changing path drops talents from the old path's subtree."""
    dropped: tuple[str, ...] = ()
    if body.time_zone is not None:
        progression.set_time_zone(db, learner.user.id, body.time_zone)
    if body.path is not None:
        dropped = progression.set_path(
            db,
            state.catalogue,
            learner.user.id,
            body.path,
            free_per_branch=state.settings.free_exercises_per_branch,
        )
    return _profile(_profile_view(db, state, learner.user.id), dropped)


@router.get("/talents")
def get_talents(learner: CurrentLearner, db: Db, state: State) -> schemas.TalentTree:
    """The general talents and the learner's own path, each allocated, available or locked."""
    return _tree(progression.talent_tree_view(db, state.catalogue, learner.user.id))


@router.post("/talents/respec")
def respec(learner: MutatingLearner, db: Db, state: State) -> schemas.TalentTree:
    """Give back every talent point."""
    return _tree(progression.respec_talents(db, state.catalogue, learner.user.id))


@router.post("/talents/{node_id}/allocation")
def allocate(node_id: str, learner: MutatingLearner, db: Db, state: State) -> schemas.TalentTree:
    """Take a talent. 409 if its requirements are not met or no points remain."""
    return _tree(progression.allocate_talent(db, state.catalogue, learner.user.id, node_id))


@router.delete("/talents/{node_id}/allocation")
def deallocate(node_id: str, learner: MutatingLearner, db: Db, state: State) -> schemas.TalentTree:
    """Give a talent back. 409 if another taken talent builds on it."""
    return _tree(progression.deallocate_talent(db, state.catalogue, learner.user.id, node_id))


@router.get("/badges")
def get_badges(learner: CurrentLearner, db: Db, state: State) -> schemas.BadgeList:
    """Every badge with how it is earned, and when it was if the learner has it."""
    return schemas.BadgeList(
        badges=[
            schemas.BadgeStatus(
                id=v.badge.id,
                title=v.badge.title,
                description=v.badge.description,
                criterion=v.description,
                requirement=_requirement(v.badge.criterion, state),
                earned=v.awarded_at is not None,
                awarded_at=v.awarded_at,
                attempt_id=v.attempt_id,
            )
            for v in progression.badge_views(db, state.catalogue, learner.user.id)
        ]
    )


@router.get("/exercises/{exercise_id}/reference-solution")
def get_reference_solution(
    exercise_id: str, learner: CurrentLearner, db: Db, state: State
) -> schemas.ReferenceSolution:
    """The reference solution and notes; 403 unless it is passed and a talent covers it."""
    solution = progression.reference_solution(db, state.catalogue, learner.user.id, exercise_id)
    return schemas.ReferenceSolution(files=solution.files, notes=solution.notes)
