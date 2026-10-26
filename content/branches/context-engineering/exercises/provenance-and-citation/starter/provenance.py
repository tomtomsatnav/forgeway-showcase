# You will need `Message` from forgeway_kit (and the `re` module).
from dataclasses import dataclass

from forgeway_kit import ModelClient


@dataclass(frozen=True)
class Piece:
    text: str
    origin: str
    ref: str


@dataclass(frozen=True)
class Reply:
    text: str
    citations: list[Piece]
    grounded: bool


def answer_with_sources(client: ModelClient, question: str, pieces: list[Piece]) -> Reply:
    """Number the pieces `[P1]`, `[P2]`... (identical ones merged), ask the question, and turn the
    labels the model cites back into the pieces they stand for."""
    raise NotImplementedError("labels out in the prompt, labels back to sources in the reply")
