from forgeway_kit import Message, ModelClient


class RollingMemory:
    """Recent messages word for word, everything older as one rolling summary."""

    def __init__(self, summariser: ModelClient, keep_recent: int = 4) -> None:
        self.summariser = summariser
        self.keep_recent = keep_recent
        self.summary = ""  # "" until the first fold
        self.recent: list[Message] = []

    def add(self, role: str, content: str) -> None:
        """Append a message; when more than `keep_recent` are pending, fold the older ones."""
        raise NotImplementedError("append, then fold all but the last keep_recent in one call")

    def messages(self) -> list[Message]:
        """The messages for the next prompt: the summary (if any), then the recent messages."""
        raise NotImplementedError("a summary message first, when there is a summary")
