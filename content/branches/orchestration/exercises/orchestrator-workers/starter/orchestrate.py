from dataclasses import dataclass

from forgeway_kit import ModelClient


class PlanError(Exception):
    """The planner's reply was not a usable plan."""


@dataclass(frozen=True)
class Orchestrated:
    plan: list[str]
    results: dict[str, str]  # subtask -> the worker's reply
    answer: str


def orchestrate(client: ModelClient, goal: str, max_subtasks: int = 5) -> Orchestrated:
    """Plan subtasks with one call, run a worker for each, then synthesise one answer.

    The planner replies with a JSON list of strings, possibly inside a ``` fence. Raise
    PlanError for anything else. Worker messages are `Goal: <goal>\\nSubtask: <subtask>`.
    The synthesis message is `Goal: <goal>` followed by a blank line and a
    `Subtask: ...\\nResult: ...` block for each subtask.
    """
    raise NotImplementedError("plan, work through the plan in order, synthesise")
