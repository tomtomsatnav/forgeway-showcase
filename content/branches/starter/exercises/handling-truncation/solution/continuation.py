from forgeway_kit import Message, ModelClient


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
    messages = [Message(role="user", content=question)]
    pieces: list[str] = []
    completion = client.complete(messages, max_tokens=max_tokens)
    pieces.append(completion.text)
    continuations = 0
    while completion.stop_reason == "max_tokens" and continuations < max_continuations:
        messages = [
            Message(role="user", content=question),
            Message(role="assistant", content="".join(pieces)),
            Message(role="user", content="Continue."),
        ]
        completion = client.complete(messages, max_tokens=max_tokens)
        pieces.append(completion.text)
        continuations += 1
    return "".join(pieces)
