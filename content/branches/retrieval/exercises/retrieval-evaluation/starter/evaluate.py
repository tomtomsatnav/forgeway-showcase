from collections.abc import Callable
from dataclasses import dataclass

Retriever = Callable[[str], list[str]]


@dataclass(frozen=True)
class Metrics:
    recall: float
    mrr: float


def recall_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    """Fraction of `relevant` ids found in the first `k` of `retrieved` (0.0 if none relevant)."""
    raise NotImplementedError


def reciprocal_rank(retrieved: list[str], relevant: set[str]) -> float:
    """1 / rank of the first relevant id (rank from 1), or 0.0 if there is none."""
    raise NotImplementedError


def evaluate(retriever: Retriever, labelled: list[tuple[str, set[str]]], k: int) -> Metrics:
    """Mean recall@k and mean reciprocal rank over every labelled query."""
    raise NotImplementedError


def best_retriever(
    retrievers: dict[str, Retriever], labelled: list[tuple[str, set[str]]], k: int
) -> str:
    """Name of the best retriever: highest recall@k, then MRR, then first listed."""
    raise NotImplementedError
