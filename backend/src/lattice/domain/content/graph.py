"""The prerequisite graph: which exercises exist, what they depend on and what is unlocked."""

from __future__ import annotations

import heapq
from collections.abc import Iterable, Mapping
from graphlib import CycleError, TopologicalSorter

from lattice.domain.content.model import Branch, BranchKind, Exercise, Tier

REQUIRE_CAPSTONES = False
"""Whether every branch that requires another must have exactly one capstone.

The default for `PrerequisiteGraph(require_capstones=...)`. It stays off so small test graphs need
no capstones, and is not flipped: the shipped content is held to the rule by
`forgeway content validate --require-capstones`, which CI runs. The other capstone rules always
apply to the capstones that exist."""

CAPSTONE_XP = range(300, 401)
CAPSTONE_MAX_TIMEOUT_S = 60
CAPSTONE_MAX_MEMORY_MB = 512


class ContentError(Exception):
    """Raised when content is invalid. Carries every problem found, not just the first."""

    def __init__(self, problems: Iterable[str]) -> None:
        self.problems = tuple(problems)
        super().__init__("\n".join(self.problems))


class PrerequisiteGraph:
    """Validated graph of branches and exercises.

    An exercise is *available* when its branch is unlocked and all of its own prerequisites
    have been passed. A branch is unlocked when every exercise in each branch it `requires`
    has been passed.

    A branch may close with one capstone: a larger project that depends, directly or not, on every
    other exercise in the branch and that nothing depends on. The root branch (the one that
    requires nothing) has none, because it is the way in. `require_capstones` makes a capstone
    mandatory in every other branch.
    """

    def __init__(
        self,
        branches: Iterable[Branch],
        exercises: Iterable[Exercise],
        *,
        require_capstones: bool = REQUIRE_CAPSTONES,
    ) -> None:
        self._require_capstones = require_capstones
        self.branches: Mapping[str, Branch] = {b.id: b for b in branches}
        self.exercises: Mapping[str, Exercise] = {e.id: e for e in exercises}
        self._order = self._validate()

    def _validate(self) -> tuple[str, ...]:
        problems: list[str] = []
        for branch in self.branches.values():
            problems.extend(
                f"branch '{branch.id}' requires unknown branch '{req}'"
                for req in branch.requires
                if req not in self.branches
            )
            if branch.kind is BranchKind.PROJECT and not branch.requires:
                problems.append(f"project branch '{branch.id}' requires no other branch")
        for ex in self.exercises.values():
            if ex.branch not in self.branches:
                problems.append(f"exercise '{ex.id}' belongs to unknown branch '{ex.branch}'")
            problems.extend(
                f"exercise '{ex.id}' has unknown prerequisite '{pre}'"
                for pre in ex.prerequisites
                if pre not in self.exercises
            )
        for branch_id in self.branches:
            if not any(e.branch == branch_id for e in self.exercises.values()):
                problems.append(f"branch '{branch_id}' has no exercises")
        problems.extend(self._capstone_problems())
        problems.extend(self._carry_problems())
        if problems:
            raise ContentError(problems)

        try:
            TopologicalSorter({b.id: b.requires for b in self.branches.values()}).static_order()
            # Exercise order must also respect branch gating, so add branch edges to exercises.
            sorter = TopologicalSorter(
                {
                    ex.id: (*ex.prerequisites, *self._gating_exercises(ex))
                    for ex in self.exercises.values()
                }
            )
            sorter.prepare()
        except CycleError as err:
            cycle = " -> ".join(str(node) for node in err.args[1])
            raise ContentError([f"prerequisite cycle: {cycle}"]) from err
        return self._ordered(sorter)

    def _capstone_problems(self) -> list[str]:
        """Every breach of the capstone rules. Unknown ids are reported separately, so they are
        skipped here."""
        problems: list[str] = []
        capstones = {e.id for e in self.exercises.values() if e.tier is Tier.CAPSTONE}
        for ex in self.exercises.values():
            problems.extend(
                f"exercise '{ex.id}' depends on capstone '{pre}'"
                for pre in ex.prerequisites
                if pre in capstones
            )
        for branch_id, branch in self.branches.items():
            own = sorted(
                e.id for e in self.exercises.values() if e.branch == branch_id and e.id in capstones
            )
            if len(own) > 1:
                problems.append(f"branch '{branch_id}' has {len(own)} capstones: {', '.join(own)}")
            if own and not branch.requires:
                problems.append(f"capstone '{own[0]}' is in '{branch_id}', which requires nothing")
            if not own and self._require_capstones and branch.requires:
                problems.append(f"branch '{branch_id}' has no capstone")
        for cap_id in sorted(capstones):
            problems.extend(self._capstone_limit_problems(self.exercises[cap_id]))
        return problems

    def _carry_problems(self) -> list[str]:
        """A `carry_from` must name an earlier exercise in the same branch that this one depends
        on, directly or not, so the files it carries are always from work already passed."""
        problems: list[str] = []
        for ex in self.exercises.values():
            source = ex.carry_from
            if source is None:
                continue
            if source not in self.exercises:
                problems.append(f"exercise '{ex.id}' carries from unknown exercise '{source}'")
            elif self.exercises[source].branch != ex.branch:
                problems.append(f"exercise '{ex.id}' carries from '{source}' in another branch")
            elif source not in self._transitive_prerequisites(ex.id):
                problems.append(
                    f"exercise '{ex.id}' carries from '{source}' but does not depend on it"
                )
        return problems

    def _capstone_limit_problems(self, cap: Exercise) -> list[str]:
        problems: list[str] = []
        covered = self._transitive_prerequisites(cap.id)
        missing = sorted(
            e.id
            for e in self.exercises.values()
            if e.branch == cap.branch and e.id != cap.id and e.id not in covered
        )
        if missing:
            problems.append(
                f"capstone '{cap.id}' does not depend on every other exercise in its branch: "
                f"missing {', '.join(missing)}"
            )
        if cap.xp not in CAPSTONE_XP:
            problems.append(
                f"capstone '{cap.id}' awards {cap.xp} XP; "
                f"capstones award {CAPSTONE_XP.start} to {CAPSTONE_XP.stop - 1}"
            )
        if cap.limits.timeout_s > CAPSTONE_MAX_TIMEOUT_S:
            problems.append(
                f"capstone '{cap.id}' allows {cap.limits.timeout_s} s; "
                f"the most is {CAPSTONE_MAX_TIMEOUT_S} s"
            )
        if cap.limits.memory_mb > CAPSTONE_MAX_MEMORY_MB:
            problems.append(
                f"capstone '{cap.id}' allows {cap.limits.memory_mb} MB; "
                f"the most is {CAPSTONE_MAX_MEMORY_MB} MB"
            )
        return problems

    def _transitive_prerequisites(self, exercise_id: str) -> set[str]:
        """Everything the exercise depends on, directly or not. Safe on cycles and unknown ids."""
        seen: set[str] = set()
        stack = list(self.exercises[exercise_id].prerequisites)
        while stack:
            node = stack.pop()
            if node not in seen and node in self.exercises:
                seen.add(node)
                stack.extend(self.exercises[node].prerequisites)
        return seen

    def _ordered(self, sorter: TopologicalSorter[str]) -> tuple[str, ...]:
        """A stable order: among exercises whose prerequisites are met, easier tiers and
        smaller XP come first, so learners meet beginner material before advanced. A capstone
        depends on everything else in its branch and ranks last, so it always closes its branch."""
        tier_rank = {tier: rank for rank, tier in enumerate(Tier)}
        order: list[str] = []
        ready: list[tuple[int, int, str]] = []
        while sorter.is_active():
            for node in sorter.get_ready():
                ex = self.exercises[node]
                heapq.heappush(ready, (tier_rank[ex.tier], ex.xp, node))
            _, _, node = heapq.heappop(ready)
            order.append(node)
            sorter.done(node)
        return tuple(order)

    def _gating_exercises(self, ex: Exercise) -> tuple[str, ...]:
        required = self.branches[ex.branch].requires
        return tuple(e.id for e in self.exercises.values() if e.branch in required)

    @property
    def order(self) -> tuple[str, ...]:
        """Exercise ids in an order where every prerequisite precedes its dependants."""
        return self._order

    def branch_exercises(self, branch_id: str) -> tuple[Exercise, ...]:
        """Exercises in a branch, in prerequisite order."""
        return tuple(
            self.exercises[i] for i in self._order if self.exercises[i].branch == branch_id
        )

    def is_branch_complete(self, branch_id: str, passed: frozenset[str]) -> bool:
        return all(e.id in passed for e in self.branch_exercises(branch_id))

    def is_branch_unlocked(self, branch_id: str, passed: frozenset[str]) -> bool:
        return all(
            self.is_branch_complete(req, passed) for req in self.branches[branch_id].requires
        )

    def is_available(self, exercise_id: str, passed: frozenset[str]) -> bool:
        """True when the learner may attempt the exercise (passed exercises stay available)."""
        ex = self.exercises[exercise_id]
        return self.is_branch_unlocked(ex.branch, passed) and all(
            pre in passed for pre in ex.prerequisites
        )

    def newly_unlocked(self, before: frozenset[str], after: frozenset[str]) -> tuple[str, ...]:
        """Exercises that became available between two sets of passed exercises."""
        return tuple(
            i
            for i in self._order
            if i not in after and self.is_available(i, after) and not self.is_available(i, before)
        )
