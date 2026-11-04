from collections.abc import Sequence
from dataclasses import dataclass, field, replace  # noqa: F401


class Usage:
    """Replace this class with the frozen dataclass the brief describes."""


def add_output(usage: Usage, extra: int) -> Usage:
    """A new Usage with `extra` more output tokens."""
    raise NotImplementedError


class Conversation:
    """Replace this class with the dataclass the brief describes."""


def find(conversations: Sequence[Conversation], title: str) -> Conversation | None:
    """The first conversation with this title, or None."""
    raise NotImplementedError
