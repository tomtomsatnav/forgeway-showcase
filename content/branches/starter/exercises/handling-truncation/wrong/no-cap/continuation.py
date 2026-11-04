from forgeway_kit import Message, ModelClient


def complete_fully(
    client: ModelClient,
    question: str,
    *,
    max_tokens: int = 50,
    max_continuations: int = 5,
) -> str:
    messages = [Message(role="user", content=question)]
    pieces = []
    while True:
        completion = client.complete(messages, max_tokens=max_tokens)
        pieces.append(completion.text)
        if completion.stop_reason != "max_tokens":
            return "".join(pieces)
        messages = [
            Message(role="user", content=question),
            Message(role="assistant", content="".join(pieces)),
            Message(role="user", content="Continue."),
        ]
