from collections.abc import Sequence

from forgeway_kit import Message, count_tokens


def fit_to_budget(system: str, messages: Sequence[Message], budget: int) -> list[Message]:
    """Trim the oldest `messages` so system prompt plus messages fit in `budget` tokens.

    The result starts with a user message and always ends with the latest message. Raises
    ValueError if even the system prompt and the latest message do not fit.
    """
    kept = list(messages)

    def total() -> int:
        return count_tokens(system) + sum(count_tokens(m.content) for m in kept)

    while len(kept) > 1 and (total() > budget or kept[0].role != "user"):
        kept.pop(0)
    if total() > budget:
        raise ValueError(
            f"the system prompt and latest message need {total()} tokens; budget is {budget}"
        )
    return kept
