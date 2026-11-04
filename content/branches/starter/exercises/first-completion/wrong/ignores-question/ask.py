from forgeway_kit import Message, ModelClient


def ask(client: ModelClient, question: str) -> str:
    completion = client.complete([Message(role="user", content="Hello")])
    return completion.text
