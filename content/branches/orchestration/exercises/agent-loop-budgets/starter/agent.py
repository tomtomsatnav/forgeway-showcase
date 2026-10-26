from collections.abc import Callable
from dataclasses import dataclass

from forgeway_kit import ModelClient, Tool


@dataclass(frozen=True)
class AgentResult:
    status: str  # "done", "token_budget", "loop_detected" or "max_steps"
    text: str
    steps: int  # model calls made
    tokens_used: int  # input plus output tokens across every call


def run_agent(
    client: ModelClient,
    task: str,
    tools: list[Tool],
    registry: dict[str, Callable[..., object]],
    *,
    max_steps: int = 8,
    token_budget: int = 2000,
    max_repeats: int = 2,
) -> AgentResult:
    """Run a tool-calling loop that stops itself: on an answer, a blown budget or a loop.

    After each model call add `usage.input_tokens + usage.output_tokens` to the total. For a
    tool request, check in this order: tokens used > `token_budget`; a call already made
    `max_repeats` times; this was call number `max_steps`. If any holds, return that status
    without running the request's tools.
    """
    raise NotImplementedError("a tool loop that checks its budgets before it acts")
