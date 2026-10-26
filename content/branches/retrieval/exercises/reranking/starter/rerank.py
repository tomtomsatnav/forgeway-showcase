from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class Candidate:
    id: str
    text: str


def rerank_search(
    retrieve: Callable[[str, int], list[Candidate]],
    scorer: Callable[[str, str], float],
    query: str,
    n: int = 10,
    k: int = 3,
) -> list[Candidate]:
    """Retrieve `n` candidates, rescore them with `scorer(query, text)`, return the best `k`.

    Each candidate is scored exactly once; ties keep retrieval order.
    """
    raise NotImplementedError("retrieve wide, score each candidate, sort, cut to k")
