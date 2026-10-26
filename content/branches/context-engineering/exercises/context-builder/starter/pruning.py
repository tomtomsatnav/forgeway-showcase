# You will need `count_tokens` from forgeway_kit.
from forgeway_kit import Message


def prune_stale(messages: list[Message], keep: int) -> list[Message]:
    """A new list in which the tool results of all but the newest `keep` rounds are replaced
    by `[pruned: {name}, {n} tokens]`, when that is shorter. No message is added or removed.

    A round is an assistant message with tool calls and the tool messages directly after it.
    """
    raise NotImplementedError("group messages into rounds, then replace content of stale ones")
