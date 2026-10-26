from typing import Any

from forgeway_kit import cosine_similarity  # noqa: F401


def hybrid_search(
    query: str,
    chunks: dict[str, str],
    mentions: dict[str, list[str]],
    edges: list[tuple[str, str, str]],
    embedder: Any,
    k: int = 3,
    vector_k: int = 3,
) -> list[tuple[str, float]]:
    """Vector search, one graph hop from what it finds, then reciprocal rank fusion."""
    raise NotImplementedError("two ranked lists, then fuse them")
