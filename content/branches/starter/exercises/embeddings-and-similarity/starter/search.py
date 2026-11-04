from collections.abc import Sequence

from forgeway_kit import Embedder


def top_k(embedder: Embedder, query: str, documents: Sequence[str], k: int = 3) -> list[str]:
    """Return the `k` documents most similar to `query`, most similar first."""
    raise NotImplementedError("embed, score with cosine_similarity, sort, take k")
