from forgeway_kit import Message, ModelClient


class Chat:
    """A multi-turn conversation that remembers what has been said."""

    def __init__(self, client: ModelClient, system: str | None = None) -> None:
        self._client = client
        self._system = system
        self._messages: list[Message] = []

    @property
    def history(self) -> list[Message]:
        """A copy of the conversation so far, oldest message first."""
        return list(self._messages)

    def send(self, text: str) -> str:
        """Add `text` as a user turn, get a reply using the full history, and record it."""
        self._messages.append(Message(role="user", content=text))
        completion = self._client.complete(self._messages, system=self._system)
        self._messages.append(Message(role="assistant", content=completion.text))
        return completion.text
