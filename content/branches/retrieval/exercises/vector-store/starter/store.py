from dataclasses import dataclass, field

from forgeway_kit import Embedder


@dataclass(frozen=True)
class Hit:
    id: str
    text: str
    score: float
    metadata: dict = field(default_factory=dict)


class VectorStore:
    def __init__(self, embedder: Embedder) -> None:
        """Keep `embedder`; it is injected so tests can supply their own."""
        raise NotImplementedError

    def add(self, doc_id: str, text: str, metadata: dict | None = None) -> None:
        """Embed and store a text. Adding an existing id replaces that entry."""
        raise NotImplementedError

    def search(self, query: str, k: int = 3) -> list[Hit]:
        """Return up to `k` hits, most similar first (cosine similarity)."""
        raise NotImplementedError
