from forgeway_kit import Embedder


class Retriever:
    """Hybrid search over chunks: vector and BM25 rankings, fused, then optionally reranked."""

    def __init__(
        self,
        chunks: list,
        embedder: Embedder,
        *,
        scorer=None,
        depth: int = 12,
        pool: int = 8,
        rrf_k: int = 60,
    ) -> None:
        """`chunks` have `.id`, `.text` and `.metadata`. `scorer(query, text)` is optional."""
        raise NotImplementedError

    def search(self, query: str, k: int = 3, where: dict | None = None) -> list:
        """The best `k` chunks for `query` among those matching `where`. See the brief."""
        raise NotImplementedError
