import re  # noqa: F401  (you will need it)
from dataclasses import dataclass
from typing import Any

from forgeway_kit import Message, ModelClient  # noqa: F401


@dataclass(frozen=True)
class Answer:
    text: str
    edges: list[Any]  # the cited edges, as the store returned them
    sources: list[str]  # their distinct sources, in order of first citation


def answer_question(
    client: ModelClient, store: Any, question: str, start: str, max_hops: int = 2
) -> Answer:
    """Walk `max_hops` hops out from `start`, show the model the edges, return cited edges."""
    raise NotImplementedError("breadth-first search, numbered facts, then map markers back")
