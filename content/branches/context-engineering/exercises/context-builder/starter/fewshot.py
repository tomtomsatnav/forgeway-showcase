# You will need `HashingEmbedder`, `cosine_similarity` and `count_tokens` from forgeway_kit.
from dataclasses import dataclass


@dataclass(frozen=True)
class Example:
    question: str
    answer: str


def choose_examples(pool: list[Example], query: str, k: int, budget: int) -> list[Example]:
    """Up to `k` examples whose questions are most like `query`, within `budget` tokens,
    best match first."""
    raise NotImplementedError("rank by similarity, then fill the budget")
