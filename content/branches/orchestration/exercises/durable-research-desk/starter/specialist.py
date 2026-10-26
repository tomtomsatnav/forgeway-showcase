"""The specialist's side: the briefing it is handed, and the tool loop it then runs."""

from collections.abc import Callable

from contracts import Desk
from journal import Ledger


def briefing(plan: list[str], results: dict[str, str], failed: dict[str, str], draft: str) -> str:
    """The second user message of the specialist's conversation (see the brief)."""
    raise NotImplementedError("say what was found, what was not, and the draft")


def run_specialist(
    ledger: Ledger,
    desk: Desk,
    request: str,
    note: str,
    registry: dict[str, Callable[..., object]],
) -> str:
    """Start the specialist's conversation (the request, then `note`) and run its tool loop.

    Compact when the conversation is large, check the budgets and for repeated calls before any
    tool runs, and pause for approval. Returns the final answer; stopping and pausing are
    signalled however you like, as long as `run_workflow` turns them into an Outcome.
    """
    raise NotImplementedError("a tool loop that compacts, obeys the budgets and asks first")
