from collections.abc import Sequence

from forgeway_kit import Message, count_tokens


def fit_to_budget(system: str, messages: Sequence[Message], budget: int) -> list[Message]:
    kept = list(messages)
    while len(kept) > 1 and (
        sum(count_tokens(m.content) for m in kept) > budget or kept[0].role != "user"
    ):
        kept.pop(0)
    return kept
