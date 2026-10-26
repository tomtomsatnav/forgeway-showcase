from forgeway_kit import Message, ModelClient


def complete_fully(
    client: ModelClient,
    question: str,
    *,
    max_tokens: int = 50,
    max_continuations: int = 5,
) -> str:
    completion = client.complete([Message(role="user", content=question)], max_tokens=max_tokens)
    return completion.text
