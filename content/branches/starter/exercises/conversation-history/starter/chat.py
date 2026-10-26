from forgeway_kit import Message, ModelClient


class Chat:
    """A multi-turn conversation that remembers what has been said."""

    def __init__(self, client: ModelClient, system: str | None = None) -> None:
        raise NotImplementedError("store the client, the system prompt and an empty history")

    @property
    def history(self) -> list[Message]:
        """A copy of the conversation so far, oldest message first."""
        raise NotImplementedError("return a copy of the stored messages")

    def send(self, text: str) -> str:
        """Add `text` as a user turn, get a reply using the full history, and record it."""
        raise NotImplementedError("send the history, record the reply, return its text")
