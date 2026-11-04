from collections.abc import Sequence
from dataclasses import dataclass, field, replace


@dataclass(frozen=True)
class Usage:
    input_tokens: int
    output_tokens: int = 0

    @property
    def total(self) -> int:
        return self.input_tokens + self.output_tokens


def add_output(usage: Usage, extra: int) -> Usage:
    """A new Usage with `extra` more output tokens."""
    return replace(usage, output_tokens=usage.output_tokens + extra)


@dataclass
class Conversation:
    title: str
    messages: list[str] = field(default_factory=list)

    def add(self, text: str) -> None:
        self.messages.append(text)


def find(conversations: Sequence[Conversation], title: str) -> Conversation | None:
    """The first conversation with this title, or None."""
    for conversation in conversations:
        if conversation.title == title:
            return conversation
    return None
