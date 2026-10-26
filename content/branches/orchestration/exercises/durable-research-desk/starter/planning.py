"""The orchestrator's side: route the request, plan it, fan workers out, draft the report."""

from contracts import Desk
from journal import Ledger


def route(ledger: Ledger, request: str, desks: dict[str, Desk], default: str) -> str:
    """One call to pick a desk: `name: description` for each, the request as the user message.
    The first desk named in the reply, as a whole word and ignoring case, else `default`."""
    raise NotImplementedError("one router call, then match the reply to a desk")


def make_plan(ledger: Ledger, desk: Desk, request: str) -> list[str]:
    """One call to plan. Strip a code fence, parse the JSON, raise PlanError for anything but a
    non-empty list of non-empty strings, then trim, drop duplicates and apply max_subtasks."""
    raise NotImplementedError("plan, then tidy the plan in code")


def fan_out(
    ledger: Ledger, desk: Desk, request: str, plan: list[str]
) -> tuple[dict[str, str], dict[str, str]]:
    """Run one worker per subtask, at the same time. Returns (results, failed): each
    subtask that worked with its reply, each that raised a ModelError with the error message."""
    raise NotImplementedError("workers in parallel, each isolated, failures kept apart")


def draft(ledger: Ledger, desk: Desk, request: str, results: dict[str, str]) -> str:
    """One call that combines the goal and every subtask's result, in plan order."""
    raise NotImplementedError("one drafting call over everything the workers found")
