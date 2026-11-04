from collections.abc import Callable
from dataclasses import dataclass

from forgeway_kit import Embedder, HashingEmbedder, ModelClient


@dataclass(frozen=True)
class Episode:
    id: int
    text: str
    importance: int  # 1 to 10, from the scorer
    created_at: float  # seconds, from the injected clock


class EpisodicStore:
    """Events scored on recency, importance and relevance."""

    def __init__(
        self,
        scorer: ModelClient,
        clock: Callable[[], float],
        embedder: Embedder | None = None,
    ) -> None:
        self.scorer = scorer
        self.clock = clock
        self.embedder = embedder or HashingEmbedder()
        self.episodes: list[Episode] = []

    def add(self, text: str) -> Episode:
        """Rate the text with the scorer, store it with the current time and return it."""
        raise NotImplementedError("ask the scorer, parse and clamp the number, store an Episode")

    def recall(self, query: str, k: int = 3) -> list[Episode]:
        """Up to k episodes, best first: recency + importance / 10 + relevance."""
        raise NotImplementedError("score every episode at the current time and sort")
