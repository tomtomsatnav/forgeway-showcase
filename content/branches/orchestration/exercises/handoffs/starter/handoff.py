from collections.abc import Callable
from dataclasses import dataclass

from forgeway_kit import ModelClient, Tool


@dataclass(frozen=True)
class Agent:
    system: str
    tools: list[Tool]
    registry: dict[str, Callable[..., object]]


@dataclass(frozen=True)
class HandoffResult:
    text: str
    agent: str  # the agent that gave the final answer
    trail: list[str]  # every agent that held the conversation, in order


def run_with_handoffs(
    client: ModelClient,
    agents: dict[str, Agent],
    start: str,
    message: str,
    max_handoffs: int = 3,
) -> HandoffResult:
    """Run `agents[start]` on `message`, passing the conversation on when it calls `handoff`.

    Offer each agent its own tools plus `handoff(to, reason, summary)`. A valid handoff starts a
    fresh conversation for the receiving agent: the original message, then a briefing. More than
    `max_handoffs` raises RuntimeError mentioning max_handoffs.
    """
    raise NotImplementedError("a tool loop that can switch the active agent")
