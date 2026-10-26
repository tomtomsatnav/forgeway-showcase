import json
from collections.abc import Mapping
from dataclasses import dataclass, field

from forgeway_kit import Message, Tool, ToolCall, count_tokens


class PlanError(Exception):
    """The planner's reply was not a usable plan."""


@dataclass(frozen=True)
class Desk:
    description: str  # shown to the router
    system: str  # the desk's house prompt: the planner, workers and drafting call start with it
    specialist: str  # the system prompt of the specialist the work is handed to
    tools: tuple[Tool, ...] = ()  # the specialist's tools
    needs_approval: frozenset[str] = frozenset()  # tool names that wait for a person


@dataclass(frozen=True)
class Limits:
    max_subtasks: int = 5
    max_workers: int = 4
    max_steps: int = 40  # model calls in the whole run
    token_budget: int = 50_000  # input plus output tokens in the whole run
    max_repeats: int = 2
    compact_at: int = 600
    keep_recent: int = 4


@dataclass(frozen=True)
class Outcome:
    status: str  # done, waiting, failed, token_budget, max_steps or loop_detected
    text: str = ""  # the specialist's final answer, when done
    pending: tuple[ToolCall, ...] = ()  # the calls needing a decision, when waiting
    desk: str = ""  # the desk the router chose
    plan: tuple[str, ...] = ()  # the tidied subtasks
    failed: Mapping[str, str] = field(default_factory=dict)  # subtask -> error message
    steps: int = 0  # model calls in the run so far, across every process that worked on it
    tokens_used: int = 0  # input plus output tokens in the run so far


def message_tokens(message: Message) -> int:
    calls = sum(count_tokens(c.name + json.dumps(dict(c.arguments))) for c in message.tool_calls)
    return count_tokens(message.content) + calls


def conversation_tokens(messages: list[Message]) -> int:
    """The tokens `messages` take up in the model's context window."""
    return sum(message_tokens(m) for m in messages)
