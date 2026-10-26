from collections.abc import Callable, Sequence

Retriever = Callable[[str, int], list[str]]


def reciprocal_rank_fusion(
    rankings: Sequence[Sequence[str]], k: int = 60
) -> list[tuple[str, float]]:
    """Fuse ranked id lists. Each appearance at 1-based `rank` adds 1 / (k + rank).

    Return (id, score) pairs, best first; ties go to the id seen first.
    """
    raise NotImplementedError


def hybrid_search(
    query: str, retrievers: Sequence[Retriever], k: int = 3, rrf_k: int = 60, depth: int = 20
) -> list[str]:
    """Run every retriever for `depth` results, fuse with RRF, return the top `k` ids."""
    raise NotImplementedError
