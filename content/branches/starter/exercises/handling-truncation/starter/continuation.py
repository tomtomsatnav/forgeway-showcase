from forgeway_kit import ModelClient


def complete_fully(
    client: ModelClient,
    question: str,
    *,
    max_tokens: int = 50,
    max_continuations: int = 5,
) -> str:
    """Answer `question`, continuing the reply whenever it is cut off by `max_tokens`.

    Makes at most `1 + max_continuations` model calls and returns the pieces joined together.
    """
    raise NotImplementedError("call, check stop_reason, continue, join")
