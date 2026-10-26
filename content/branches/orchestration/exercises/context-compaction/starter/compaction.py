import json
from collections.abc import Callable

from forgeway_kit import Message, ModelClient, Tool, count_tokens


def message_tokens(message: Message) -> int:
    calls = sum(count_tokens(c.name + json.dumps(dict(c.arguments))) for c in message.tool_calls)
    return count_tokens(message.content) + calls


def conversation_tokens(messages: list[Message]) -> int:
    """The tokens `messages` take up in the model's context window."""
    return sum(message_tokens(m) for m in messages)


def run_long_task(
    client: ModelClient,
    task: str,
    tools: list[Tool],
    registry: dict[str, Callable[..., object]],
    *,
    compact_at: int = 500,
    keep_recent: int = 4,
    max_steps: int = 40,
) -> str:
    """A tool loop that summarises its older messages when the conversation grows too large.

    Before each model call, if the conversation is over `compact_at` tokens, replace everything
    between the task and the last `keep_recent` messages with one user message that starts
    `Summary of earlier work:`. Never leave a `tool` message first in the recent part.
    """
    raise NotImplementedError("a tool loop that compacts its history before it overflows")
