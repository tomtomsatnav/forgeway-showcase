from chunking import Chunk, chunk_article  # noqa: F401

from forgeway_kit import Embedder


class KnowledgeBase:
    """The help centre, chunked and indexed for hybrid search with metadata filters."""

    def __init__(
        self, embedder: Embedder, *, depth: int = 10, rrf_k: int = 60, max_chars: int = 300
    ) -> None:
        raise NotImplementedError

    def upsert(self, article: dict) -> int:
        """Store an article, replacing any earlier version; return how many chunks it gave."""
        raise NotImplementedError

    def remove(self, article_id: str) -> bool:
        """Drop an article and all its chunks; True if it was stored."""
        raise NotImplementedError

    def article(self, article_id: str) -> dict | None:
        """The article as it was last upserted, or None."""
        raise NotImplementedError

    def search(self, query: str, k: int = 5, where: dict | None = None) -> list[Chunk]:
        """The best `k` chunks for `query` among those matching `where`. See the brief."""
        raise NotImplementedError
