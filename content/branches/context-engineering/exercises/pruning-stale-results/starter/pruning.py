# You will need `Message` and `count_tokens` from forgeway_kit.
from collections.abc import Callable

from forgeway_kit import Message, ModelClient, Tool


def prune_stale(messages: list[Message], keep: int) -> list[Message]:
    """A new list in which the tool results of all but the newest `keep` rounds are replaced
    by `[pruned: {name}, {n} tokens]`, when that is shorter. No message is added or removed."""
    raise NotImplementedError("group messages into rounds, then replace content of stale ones")


def run_pruned(
    client: ModelClient,
    task: str,
    tools: list[Tool],
    registry: dict[str, Callable[..., object]],
    keep: int = 2,
    max_steps: int = 20,
) -> str:
    """A tool loop that prunes its stored history before every model call."""
    raise NotImplementedError("prune, ask, answer the calls, repeat")
