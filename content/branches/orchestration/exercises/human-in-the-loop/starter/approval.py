from collections.abc import Callable
from dataclasses import dataclass

from forgeway_kit import ModelClient, Tool, ToolCall


@dataclass(frozen=True)
class Outcome:
    status: str  # "done" or "waiting"
    text: str = ""  # the final answer, when done
    pending: tuple[ToolCall, ...] = ()  # the calls needing a decision, when waiting


class ApprovalAgent:
    def __init__(
        self,
        client: ModelClient,
        tools: list[Tool],
        registry: dict[str, Callable[..., object]],
        needs_approval: set[str],
    ) -> None:
        self.client = client
        self.tools = tools
        self.registry = registry
        self.needs_approval = needs_approval

    def start(self, task: str) -> Outcome:
        """Begin a conversation. Pause, running nothing, when a request needs approval."""
        raise NotImplementedError("loop until the model answers or asks for a risky tool")

    def resume(self, decisions: dict[str, bool | str]) -> Outcome:
        """Apply a person's decisions to the waiting request, then carry on."""
        raise NotImplementedError("validate the decisions, run the request, continue the loop")
