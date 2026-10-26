"""Paths, talents, badges and reference solutions: the learner's character-building use cases."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import delete, exists, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session, aliased

from lattice.application.errors import (
    ConflictError,
    ForbiddenError,
    InvalidInputError,
    NotFoundError,
)
from lattice.application.learning import learner_unlocks, passed_exercises, total_xp
from lattice.application.plans import Unlocks
from lattice.application.streak import GRADED, streak_for, validate_time_zone
from lattice.domain.content import Tier
from lattice.domain.progression import (
    GENERAL,
    GENERALIST,
    Badge,
    Blocker,
    LearnerFacts,
    NodeStatus,
    TalentNode,
    TalentState,
    active_allocations,
    active_titles,
    can_allocate,
    can_deallocate,
    kept_after_path_change,
    level_progress,
    newly_earned,
    node_status,
    points_available,
    points_spent,
    reference_solution_branches,
    talent_points,
)
from lattice.domain.progression.talents import ReferenceSolutionsEffect
from lattice.infrastructure.content_loader import ContentCatalogue
from lattice.infrastructure.db.engine import rowcount
from lattice.infrastructure.db.models import (
    Attempt,
    BadgeAward,
    ExerciseProgress,
    LearnerProfile,
    TalentAllocation,
    XpEvent,
)

# --- Profile: path and time zone ---------------------------------------------------------------


@dataclass(frozen=True)
class PathOption:
    id: str
    title: str
    summary: str
    home_branch: str | None
    selectable: bool
    reason: str | None  # why it cannot be chosen yet, in neutral words
    # The branches (id, title) to complete before it can be chosen, so a client words it itself.
    requires: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class ProfileView:
    path: str
    time_zone: str
    titles: tuple[str, ...]
    paths: tuple[PathOption, ...]


def _profile(session: Session, user_id: uuid.UUID, *, lock: bool = False) -> LearnerProfile:
    profile = session.get(LearnerProfile, user_id, with_for_update=lock)
    if profile is None:
        raise NotFoundError("No such learner.")
    return profile


def current_path(catalogue: ContentCatalogue, profile: LearnerProfile) -> str:
    """The learner's path; one that no longer exists in content falls back to the generalist."""
    path = profile.path_choice or GENERALIST
    return path if path in catalogue.progression.tree.path_ids else GENERALIST


def profile_view(
    session: Session, catalogue: ContentCatalogue, user_id: uuid.UUID, *, free_per_branch: int
) -> ProfileView:
    profile = _profile(session, user_id)
    tree = catalogue.progression.tree
    opens = learner_unlocks(
        session,
        catalogue,
        user_id,
        passed_exercises(session, user_id),
        free_per_branch=free_per_branch,
    )
    # Mode-neutral: no "branch", "track" or "zone", since both modes show it as it is.
    options = [
        PathOption(GENERALIST, "Generalist", "Ranges across every subject.", None, True, None)
    ]
    graph = catalogue.graph
    for spec in tree.paths.values():
        reason = _path_blocker(catalogue, spec.home_branch, opens)
        requires = (
            ()
            if reason is None
            else tuple(
                (b, graph.branches[b].title) for b in graph.branches[spec.home_branch].requires
            )
        )
        options.append(
            PathOption(
                spec.id,
                spec.title,
                spec.summary,
                spec.home_branch,
                reason is None,
                reason,
                requires,
            )
        )
    state = _talent_state(session, catalogue, user_id)
    return ProfileView(
        path=state.path,
        time_zone=profile.time_zone,
        titles=active_titles(tree, state),
        paths=tuple(options),
    )


def _path_blocker(catalogue: ContentCatalogue, home_branch: str, opens: Unlocks) -> str | None:
    graph = catalogue.graph
    if opens.is_branch_unlocked(home_branch):
        return None
    titles = " and ".join(graph.branches[b].title for b in graph.branches[home_branch].requires)
    return f"Complete {titles} first."


def set_path(
    session: Session,
    catalogue: ContentCatalogue,
    user_id: uuid.UUID,
    path: str,
    *,
    free_per_branch: int,
) -> tuple[str, ...]:
    """Choose a path. Changing it is free but drops allocations in the old path's subtree.

    A specialisation needs its home branch unlocked; the generalist path is always available.
    Returns the ids of the talents that were dropped.
    """
    tree = catalogue.progression.tree
    if path not in tree.path_ids:
        raise InvalidInputError(f"There is no path called '{path}'.")
    profile = _profile(session, user_id, lock=True)
    if path != GENERALIST:
        opens = learner_unlocks(
            session,
            catalogue,
            user_id,
            passed_exercises(session, user_id),
            free_per_branch=free_per_branch,
        )
        reason = _path_blocker(catalogue, tree.paths[path].home_branch, opens)
        if reason:
            raise ForbiddenError(reason)
    allocated = _allocated(session, user_id)
    kept = set(kept_after_path_change(tree, allocated, path))
    dropped = tuple(n for n in allocated if n not in kept)
    if dropped:
        session.execute(
            delete(TalentAllocation).where(
                TalentAllocation.user_id == user_id, TalentAllocation.node_id.in_(dropped)
            )
        )
    profile.path_choice = path
    return dropped


def set_time_zone(session: Session, user_id: uuid.UUID, name: str) -> None:
    """Change the zone used for future attempts and for "today". Past days are never rewritten."""
    validate_time_zone(name)
    _profile(session, user_id).time_zone = name


# --- Talents ------------------------------------------------------------------------------------


@dataclass(frozen=True)
class TalentNodeView:
    node: TalentNode
    status: NodeStatus


@dataclass(frozen=True)
class TalentTreeView:
    path: str
    total_points: int
    spent_points: int
    available_points: int
    nodes: tuple[TalentNodeView, ...]  # the general subtree and the learner's own path


def _allocated(session: Session, user_id: uuid.UUID) -> tuple[str, ...]:
    return tuple(
        session.scalars(
            select(TalentAllocation.node_id)
            .where(TalentAllocation.user_id == user_id)
            .order_by(TalentAllocation.id)
        )
    )


def _talent_state(session: Session, catalogue: ContentCatalogue, user_id: uuid.UUID) -> TalentState:
    return TalentState(
        level=level_progress(total_xp(session, user_id)).level,
        path=current_path(catalogue, _profile(session, user_id)),
        passed=passed_exercises(session, user_id),
        allocated=_allocated(session, user_id),
    )


def talent_tree_view(
    session: Session, catalogue: ContentCatalogue, user_id: uuid.UUID
) -> TalentTreeView:
    tree = catalogue.progression.tree
    state = _talent_state(session, catalogue, user_id)
    return TalentTreeView(
        path=state.path,
        total_points=talent_points(state.level),
        spent_points=points_spent(tree, state),
        available_points=points_available(tree, state),
        nodes=tuple(
            TalentNodeView(node, node_status(tree, node.id, state))
            for node in tree.nodes.values()
            if tree.in_subtree(node, state.path)
        ),
    )


def allocate_talent(
    session: Session, catalogue: ContentCatalogue, user_id: uuid.UUID, node_id: str
) -> TalentTreeView:
    tree = catalogue.progression.tree
    if node_id not in tree.nodes:
        raise NotFoundError(f"No talent called '{node_id}'.")
    _profile(session, user_id, lock=True)  # serialises allocation so the budget cannot be overspent
    state = _prune_inactive(session, catalogue, user_id)
    decision = can_allocate(tree, node_id, state)
    if not decision.allowed:
        raise ConflictError(_explain(decision.blockers))
    session.add(TalentAllocation(user_id=user_id, node_id=node_id))
    session.flush()
    return talent_tree_view(session, catalogue, user_id)


def deallocate_talent(
    session: Session, catalogue: ContentCatalogue, user_id: uuid.UUID, node_id: str
) -> TalentTreeView:
    tree = catalogue.progression.tree
    if node_id not in tree.nodes:
        raise NotFoundError(f"No talent called '{node_id}'.")
    _profile(session, user_id, lock=True)
    state = _prune_inactive(session, catalogue, user_id)
    decision = can_deallocate(tree, node_id, state)
    if not decision.allowed:
        raise ConflictError(_explain(decision.blockers))
    session.execute(
        delete(TalentAllocation).where(
            TalentAllocation.user_id == user_id, TalentAllocation.node_id == node_id
        )
    )
    session.flush()
    return talent_tree_view(session, catalogue, user_id)


def respec_talents(
    session: Session, catalogue: ContentCatalogue, user_id: uuid.UUID
) -> TalentTreeView:
    """Give back every talent point. Free and unlimited, which is why talents never affect XP."""
    _profile(session, user_id, lock=True)
    session.execute(delete(TalentAllocation).where(TalentAllocation.user_id == user_id))
    session.flush()
    return talent_tree_view(session, catalogue, user_id)


def _prune_inactive(
    session: Session, catalogue: ContentCatalogue, user_id: uuid.UUID
) -> TalentState:
    """Drop stored allocations that no longer count (content changed under the learner)."""
    state = _talent_state(session, catalogue, user_id)
    active = active_allocations(catalogue.progression.tree, state)
    stale = [n for n in state.allocated if n not in active]
    if stale:
        session.execute(
            delete(TalentAllocation).where(
                TalentAllocation.user_id == user_id, TalentAllocation.node_id.in_(stale)
            )
        )
        return TalentState(state.level, state.path, state.passed, active)
    return state


def _explain(blockers: tuple[Blocker, ...]) -> str:
    return " ".join(b.detail for b in blockers)


# --- Reference solutions -----------------------------------------------------------------------


@dataclass(frozen=True)
class ReferenceSolution:
    files: dict[str, str]
    notes: str


def reference_solution(
    session: Session, catalogue: ContentCatalogue, user_id: uuid.UUID, exercise_id: str
) -> ReferenceSolution:
    """The reference solution, for a passed exercise in a branch a taken talent covers."""
    source = catalogue.sources.get(exercise_id)
    if source is None:
        raise NotFoundError(f"No exercise called '{exercise_id}'.")
    if exercise_id not in passed_exercises(session, user_id):
        raise ForbiddenError("Pass this exercise to read its reference solution.")
    tree = catalogue.progression.tree
    state = _talent_state(session, catalogue, user_id)
    branch = source.exercise.branch
    if branch not in reference_solution_branches(tree, state):
        # Every talent that would unlock it, the learner's own path first, each with the path it
        # belongs to (None when every path shares it), so a client can name the class to take.
        granting = sorted(
            (
                n
                for n in tree.nodes.values()
                if any(
                    isinstance(e, ReferenceSolutionsEffect) and e.reference_solutions == branch
                    for e in n.effects
                )
            ),
            key=lambda n: not tree.in_subtree(n, state.path),
        )
        titles = " or ".join(n.title for n in granting)
        hint = f" Take {titles} to unlock it." if granting else ""
        # Mode-neutral: clients word the hint themselves from `talents`.
        raise ForbiddenError(
            f"This reference solution is locked.{hint}",
            {
                "talents": [
                    {
                        "id": n.id,
                        "title": n.title,
                        "path": None if n.subtree == GENERAL else n.subtree,
                    }
                    for n in granting
                ]
            },
        )
    return ReferenceSolution(files=source.solution(), notes=source.notes())


# --- Badges -------------------------------------------------------------------------------------


@dataclass(frozen=True)
class BadgeView:
    badge: Badge
    description: str  # the criterion in words
    awarded_at: datetime | None
    attempt_id: uuid.UUID | None


def learner_facts(
    session: Session, catalogue: ContentCatalogue, user_id: uuid.UUID
) -> LearnerFacts:
    graph = catalogue.graph
    passed = passed_exercises(session, user_id)
    passing, earlier = aliased(Attempt), aliased(Attempt)
    first_try = session.scalar(
        select(func.count())
        .select_from(ExerciseProgress)
        .join(passing, passing.id == ExerciseProgress.passing_attempt_id)
        .where(
            ExerciseProgress.user_id == user_id,
            ~exists().where(
                earlier.user_id == passing.user_id,
                earlier.exercise_id == passing.exercise_id,
                earlier.status.in_(GRADED),
                earlier.created_at < passing.created_at,
            ),
        )
    )
    no_hint = session.scalar(
        select(func.count()).where(XpEvent.user_id == user_id, XpEvent.reason == "no-hints")
    )
    return LearnerFacts(
        completed_branches=frozenset(
            b for b in graph.branches if graph.is_branch_complete(b, passed)
        ),
        exercises_passed=len(passed),
        capstones_passed=sum(
            1 for i in passed if i in graph.exercises and graph.exercises[i].tier is Tier.CAPSTONE
        ),
        first_try_passes=first_try or 0,
        no_hint_passes=no_hint or 0,
        longest_streak=streak_for(session, user_id).longest,
        level=level_progress(total_xp(session, user_id)).level,
    )


def evaluate_badges(
    session: Session, catalogue: ContentCatalogue, user_id: uuid.UUID, attempt_id: uuid.UUID
) -> list[Badge]:
    """Award every badge the learner now qualifies for, crediting `attempt_id`.

    Idempotent: (user, badge) is unique, so a badge is awarded once however often this runs, and
    only badges actually inserted by this call are returned.
    """
    badges = catalogue.progression.badges
    awarded = set(session.scalars(select(BadgeAward.badge_id).where(BadgeAward.user_id == user_id)))
    earned = newly_earned(learner_facts(session, catalogue, user_id), awarded, badges)
    inserted: list[Badge] = []
    for badge in earned:
        result = session.execute(
            insert(BadgeAward)
            .values(user_id=user_id, badge_id=badge.id, attempt_id=attempt_id)
            .on_conflict_do_nothing(constraint="uq_badge_once")
        )
        if rowcount(result):
            inserted.append(badge)
    return inserted


def badge_views(
    session: Session, catalogue: ContentCatalogue, user_id: uuid.UUID
) -> list[BadgeView]:
    """Every badge, earned or not, in definition order."""
    awards = {
        a.badge_id: a
        for a in session.scalars(select(BadgeAward).where(BadgeAward.user_id == user_id))
    }
    titles = {b.id: b.title for b in catalogue.graph.branches.values()}
    return [
        BadgeView(
            badge=badge,
            description=badge.criterion.describe(titles),
            awarded_at=awards[badge.id].awarded_at if badge.id in awards else None,
            attempt_id=awards[badge.id].attempt_id if badge.id in awards else None,
        )
        for badge in catalogue.progression.badges
    ]
