"""Paths and the talent tree.

A *path* is how a learner has chosen to specialise: `generalist` (the default) or one of the
specialisations defined in content, each with a home branch and its own talent subtree. Talents
recognise demonstrated skill and never touch scoring, so XP stays a clean signal of passed work:
with free respecs, any scoring effect would simply be respecced into before each pass.

Points are derived from level, never stored. A node needs a minimum level, its parent nodes and
*passed exercises*. If content changes so that more points are spent than are available, the
newest allocations beyond the budget are inactive until the learner respecs; nothing is deleted.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from graphlib import CycleError, TopologicalSorter
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from lattice.domain.content import ContentError, PrerequisiteGraph
from lattice.domain.content.model import ExerciseId, Slug
from lattice.domain.progression.levels import MAX_LEVEL

GENERALIST = "generalist"  # the default path; it has no subtree of its own
GENERAL = "general"  # the subtree open to every path

NodeState = Literal["allocated", "available", "locked"]


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class TitleEffect(_Frozen):
    """A title shown on the learner's profile."""

    title: Annotated[str, StringConstraints(min_length=1, max_length=60)]


class ReferenceSolutionsEffect(_Frozen):
    """Lets the learner read the reference solution for passed exercises in a branch."""

    reference_solutions: Slug


Effect = TitleEffect | ReferenceSolutionsEffect


class Specialisation(_Frozen):
    id: Slug
    title: Annotated[str, StringConstraints(min_length=1, max_length=60)]
    summary: str
    home_branch: Slug


class TalentNode(_Frozen):
    id: Slug
    title: Annotated[str, StringConstraints(min_length=1, max_length=60)]
    summary: str
    subtree: Slug = GENERAL  # `general`, or the id of the specialisation it belongs to
    parents: tuple[Slug, ...] = ()
    min_level: Annotated[int, Field(ge=1, le=MAX_LEVEL)] = 2
    required_exercises: tuple[ExerciseId, ...] = ()
    effects: Annotated[tuple[Effect, ...], Field(min_length=1)]


def talent_points(level: int) -> int:
    """One point per level from level 2."""
    return max(0, level - 1)


class TalentTree:
    """Validated paths and talent nodes. Construction raises `ContentError` with every problem."""

    def __init__(
        self,
        specialisations: Iterable[Specialisation],
        nodes: Iterable[TalentNode],
        graph: PrerequisiteGraph,
    ) -> None:
        specialisations, nodes = tuple(specialisations), tuple(nodes)
        self.paths: Mapping[str, Specialisation] = {s.id: s for s in specialisations}
        self.nodes: Mapping[str, TalentNode] = {n.id: n for n in nodes}
        self.graph = graph
        problems = _problems(specialisations, nodes, graph)
        if problems:
            raise ContentError(problems)

    @property
    def path_ids(self) -> tuple[str, ...]:
        return (GENERALIST, *self.paths)

    def children(self, node_id: str) -> tuple[str, ...]:
        return tuple(n.id for n in self.nodes.values() if node_id in n.parents)

    def in_subtree(self, node: TalentNode, path: str) -> bool:
        """True when a learner on `path` may use the node."""
        return node.subtree in (GENERAL, path)


def _problems(
    specialisations: Sequence[Specialisation],
    nodes: Sequence[TalentNode],
    graph: PrerequisiteGraph,
) -> list[str]:
    problems: list[str] = []
    path_ids = {s.id for s in specialisations}
    if len(path_ids) != len(specialisations):
        problems.append("a path id is defined more than once")
    for spec in specialisations:
        if spec.id in (GENERALIST, GENERAL):
            problems.append(f"path id '{spec.id}' is reserved")
        if spec.home_branch not in graph.branches:
            problems.append(f"path '{spec.id}' has unknown home branch '{spec.home_branch}'")

    by_id = {n.id: n for n in nodes}
    if len(by_id) != len(nodes):
        problems.append("a talent id is defined more than once")
    for node in nodes:
        problems.extend(_node_problems(node, by_id, path_ids, graph))

    try:
        TopologicalSorter({n.id: [p for p in n.parents if p in by_id] for n in nodes}).prepare()
    except CycleError as err:
        problems.append(f"talent cycle: {' -> '.join(str(n) for n in err.args[1])}")
    return problems


def _node_problems(
    node: TalentNode,
    by_id: Mapping[str, TalentNode],
    path_ids: set[str],
    graph: PrerequisiteGraph,
) -> list[str]:
    where = f"talent '{node.id}'"
    problems: list[str] = []
    if node.subtree != GENERAL and node.subtree not in path_ids:
        problems.append(f"{where} belongs to unknown path '{node.subtree}'")
    for parent_id in node.parents:
        parent = by_id.get(parent_id)
        if parent is None:
            problems.append(f"{where} has unknown parent '{parent_id}'")
        elif parent_id == node.id:
            problems.append(f"{where} cannot be its own parent")
        elif parent.subtree not in (GENERAL, node.subtree):
            problems.append(
                f"{where} in subtree '{node.subtree}' has parent '{parent_id}' in a different "
                f"subtree '{parent.subtree}'"
            )
    problems.extend(
        f"{where} requires unknown exercise '{ex}'"
        for ex in node.required_exercises
        if ex not in graph.exercises
    )
    problems.extend(
        f"{where} grants reference solutions for unknown branch '{effect.reference_solutions}'"
        for effect in node.effects
        if isinstance(effect, ReferenceSolutionsEffect)
        and effect.reference_solutions not in graph.branches
    )
    return problems


@dataclass(frozen=True)
class TalentState:
    """The facts the allocation rules need."""

    level: int
    path: str
    passed: frozenset[str]
    allocated: tuple[str, ...]  # node ids, oldest first


class BlockerCode(StrEnum):
    UNKNOWN_NODE = "unknown-node"
    ALREADY_ALLOCATED = "already-allocated"
    NOT_ALLOCATED = "not-allocated"
    OTHER_PATH = "other-path"
    LEVEL = "level"
    PARENTS = "parents"
    EXERCISES = "exercises"
    NO_POINTS = "no-points"
    DEPENDANTS = "dependants"


@dataclass(frozen=True)
class Blocker:
    code: BlockerCode
    detail: str


@dataclass(frozen=True)
class Decision:
    blockers: tuple[Blocker, ...] = ()

    @property
    def allowed(self) -> bool:
        return not self.blockers


@dataclass(frozen=True)
class NodeStatus:
    state: NodeState
    blockers: tuple[Blocker, ...]


def active_allocations(tree: TalentTree, state: TalentState) -> tuple[str, ...]:
    """The allocations that count: known, on the learner's path, with their parents active and
    within the points budget. When over budget, the newest allocations are the inactive ones."""
    budget = talent_points(state.level)
    active: list[str] = []
    for node_id in state.allocated:
        if len(active) >= budget:
            break
        node = tree.nodes.get(node_id)
        if node and tree.in_subtree(node, state.path) and all(p in active for p in node.parents):
            active.append(node_id)
    return tuple(active)


def points_spent(tree: TalentTree, state: TalentState) -> int:
    return len(active_allocations(tree, state))


def points_available(tree: TalentTree, state: TalentState) -> int:
    """Points still to spend; never negative."""
    return max(0, talent_points(state.level) - points_spent(tree, state))


def can_allocate(tree: TalentTree, node_id: str, state: TalentState) -> Decision:
    """Whether the learner may take the talent now, with every reason it is blocked."""
    node = tree.nodes.get(node_id)
    if node is None:
        return Decision((Blocker(BlockerCode.UNKNOWN_NODE, f"There is no talent '{node_id}'."),))
    active = active_allocations(tree, state)
    if node_id in active:
        return Decision((Blocker(BlockerCode.ALREADY_ALLOCATED, "Already taken."),))

    blockers: list[Blocker] = []
    if not tree.in_subtree(node, state.path):
        spec = tree.paths[node.subtree]
        blockers.append(Blocker(BlockerCode.OTHER_PATH, f"Needs the {spec.title} path."))
    if state.level < node.min_level:
        blockers.append(Blocker(BlockerCode.LEVEL, f"Needs level {node.min_level}."))
    missing_parents = [tree.nodes[p].title for p in node.parents if p not in active]
    if missing_parents:
        blockers.append(Blocker(BlockerCode.PARENTS, f"Needs {', '.join(missing_parents)} first."))
    missing = [
        tree.graph.exercises[e].title for e in node.required_exercises if e not in state.passed
    ]
    if missing:
        blockers.append(Blocker(BlockerCode.EXERCISES, f"Pass {', '.join(missing)} first."))
    if points_available(tree, state) == 0:
        blockers.append(Blocker(BlockerCode.NO_POINTS, "No talent points to spend."))
    return Decision(tuple(blockers))


def can_deallocate(tree: TalentTree, node_id: str, state: TalentState) -> Decision:
    """A talent can be given back unless another taken talent builds on it."""
    active = active_allocations(tree, state)
    if node_id not in active:
        return Decision((Blocker(BlockerCode.NOT_ALLOCATED, "This talent is not taken."),))
    dependants = [tree.nodes[c].title for c in tree.children(node_id) if c in active]
    if dependants:
        detail = f"{', '.join(dependants)} builds on this talent."
        return Decision((Blocker(BlockerCode.DEPENDANTS, detail),))
    return Decision()


def node_status(tree: TalentTree, node_id: str, state: TalentState) -> NodeStatus:
    decision = can_allocate(tree, node_id, state)
    if node_id in active_allocations(tree, state):
        return NodeStatus("allocated", ())
    return NodeStatus("available" if decision.allowed else "locked", decision.blockers)


def kept_after_path_change(
    tree: TalentTree, allocated: Sequence[str], new_path: str
) -> tuple[str, ...]:
    """Allocations that survive a change of path: general talents stay, the old subtree goes."""
    return tuple(
        n for n in allocated if (node := tree.nodes.get(n)) and tree.in_subtree(node, new_path)
    )


def active_titles(tree: TalentTree, state: TalentState) -> tuple[str, ...]:
    """Profile titles granted by the active talents, in the order they were taken."""
    return tuple(
        effect.title
        for node_id in active_allocations(tree, state)
        for effect in tree.nodes[node_id].effects
        if isinstance(effect, TitleEffect)
    )


def reference_solution_branches(tree: TalentTree, state: TalentState) -> frozenset[str]:
    """Branches whose reference solutions the learner may read (for exercises they have passed)."""
    return frozenset(
        effect.reference_solutions
        for node_id in active_allocations(tree, state)
        for effect in tree.nodes[node_id].effects
        if isinstance(effect, ReferenceSolutionsEffect)
    )
