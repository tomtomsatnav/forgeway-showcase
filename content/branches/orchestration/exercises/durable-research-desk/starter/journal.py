"""The record of a run, shared by every stage.

This is where a run remembers what it has done, so that a new process can carry on instead of
starting again, and where its steps and tokens are counted, so that the budgets belong to the
whole run. Design it first; the other files will use it.
"""

from forgeway_kit import ToolCall


class Stopped(Exception):
    """The run must stop with this status: a budget was spent, or a call is being repeated."""

    def __init__(self, status: str) -> None:
        super().__init__(status)
        self.status = status


class Waiting(Exception):
    """The run is paused until a person decides about these calls."""

    def __init__(self, pending: tuple[ToolCall, ...]) -> None:
        super().__init__("waiting for a decision")
        self.pending = pending


class Ledger:
    """What a run knows about itself: saved model replies and tool results, saved decisions,
    and the steps and tokens spent so far. Everything that must outlive a process lives in the
    store as JSON text, saved as soon as it happens."""

    def __init__(self) -> None:
        raise NotImplementedError("decide what the record holds, then build it")
