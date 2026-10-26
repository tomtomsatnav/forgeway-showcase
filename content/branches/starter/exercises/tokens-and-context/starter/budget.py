from collections.abc import Sequence

from forgeway_kit import Message


def fit_to_budget(system: str, messages: Sequence[Message], budget: int) -> list[Message]:
    """Trim the oldest `messages` so system prompt plus messages fit in `budget` tokens.

    The result starts with a user message and always ends with the latest message. Raises
    ValueError if even the system prompt and the latest message do not fit.
    """
    raise NotImplementedError("drop the oldest messages until the request fits")
