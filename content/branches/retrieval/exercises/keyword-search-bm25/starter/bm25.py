class BM25:
    def __init__(self, documents: dict[str, str], k1: float = 1.5, b: float = 0.75) -> None:
        """Index `documents` (id -> text). Precompute whatever search will need."""
        raise NotImplementedError

    def search(self, query: str, k: int = 3) -> list[tuple[str, float]]:
        """Return up to `k` (id, score) pairs, best first, with score > 0 only."""
        raise NotImplementedError
