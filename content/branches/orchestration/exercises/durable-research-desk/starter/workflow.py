"""The entry point: run the stages in order, resume a run, take a person's decisions."""

from collections.abc import Callable, MutableMapping

from contracts import Desk, Limits, Outcome, PlanError

from forgeway_kit import ModelClient

__all__ = ["Desk", "Limits", "Outcome", "PlanError", "run_workflow"]


def run_workflow(
    client: ModelClient,
    run_id: str,
    request: str,
    *,
    desks: dict[str, Desk],
    default: str,
    registry: dict[str, Callable[..., object]],
    store: MutableMapping[str, str],
    limits: Limits | None = None,
    decisions: dict[str, bool | str] | None = None,
) -> Outcome:
    """Route, plan, fan out, draft, hand over to the specialist, and report an Outcome.

    If `store` already holds `run_id`, this is a resume: carry on from the record, whatever
    process wrote it. `decisions` answers a run that is waiting for a person.
    """
    raise NotImplementedError("run the stages against one record of the run")
