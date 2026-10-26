# You will need `Message` from forgeway_kit.
from dataclasses import dataclass

from forgeway_kit import ModelClient


@dataclass(frozen=True)
class Chunk:
    id: str
    text: str
    score: float


def place(chunks: list[Chunk]) -> list[Chunk]:
    """A new list: the best chunk first, the second best last, the third best second, and so on
    inwards, so the weakest chunks end up in the middle. Equal scores keep their input order."""
    raise NotImplementedError("rank by score, then deal ranks out to the two ends")


def ask(client: ModelClient, question: str, chunks: list[Chunk]) -> str:
    """Send the placed chunks (one `[id] text` line each), a blank line, then `Question: ...`
    as a single user message, and return the model's text."""
    raise NotImplementedError("place the chunks, then build the prompt")
