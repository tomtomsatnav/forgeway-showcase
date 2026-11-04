from forgeway_kit import Message, ModelClient


def ask(client: ModelClient, question: str) -> str:
    """Send `question` to the model and return its reply."""
    completion = client.complete([Message(role="user", content=question)])
    return completion.text
