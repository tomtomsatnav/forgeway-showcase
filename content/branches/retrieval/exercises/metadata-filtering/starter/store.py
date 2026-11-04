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
        self._embedder = embedder
        self._entries: list[tuple[str, str, list[float], dict]] = []

    def add(self, doc_id: str, text: str, metadata: dict | None = None) -> None:
        vector = self._embedder.embed([text])[0]
        self._entries.append((doc_id, text, vector, dict(metadata or {})))

    def search(self, query: str, k: int = 3, where: dict | None = None) -> list[Hit]:
        """Return up to `k` hits, most similar first, among entries matching `where`.

        `where` maps a field to a value (equality) or to {"in": [values]}. All conditions must
        hold, and an entry without the field does not match. Filter before taking the top `k`.
        """
        raise NotImplementedError("filter the entries, then score and rank them")
